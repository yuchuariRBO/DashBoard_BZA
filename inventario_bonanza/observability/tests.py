import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from gestion_personal.models import Organization
from prometheus_client.parser import text_string_to_metric_families
from support.models import SupportAudit

from .alerts import evaluate
from .middleware import MetricsMiddleware, _seen, record_activity
from .models import AlertEvent, AlertIncident, AlertRule, UserActivity
from .permissions import can_monitor
from .snapshot import snapshot


@override_settings(SECURE_SSL_REDIRECT=False)
class MonitoringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username="monitor-admin", user_type="global_admin"
        )
        cls.org = Organization.objects.create(
            name="Monitor tenant", slug="monitor-tenant"
        )
        cls.user = User.objects.create_user(
            username="monitor-user", user_type="rh", organization=cls.org
        )
        cls.scoped = User.objects.create_user(
            username="monitor-scoped", user_type="global_admin", organization=cls.org
        )

    def setUp(self):
        from django.core.cache import caches

        caches["monitoring"].clear()
        import observability.snapshot as snapshots

        snapshots._cached = None

    def test_only_authorized_admins_can_access_monitoring_and_grafana(self):
        for user in (self.user, self.scoped):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(reverse("observability:dashboard")).status_code, 403
            )
            with override_settings(GRAFANA_URL="https://grafana.example.test"):
                self.assertEqual(
                    self.client.get(
                        reverse("observability:grafana", args=["general"])
                    ).status_code,
                    403,
                )
            self.assertEqual(
                self.client.get(reverse("observability:rules")).status_code, 403
            )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("observability:dashboard")).status_code, 200
        )

    def test_explicit_monitoring_permission_and_tenant_boundary(self):
        permission = Permission.objects.get(
            codename="view_monitoring", content_type__app_label="observability"
        )
        self.scoped.user_permissions.add(permission)
        self.assertFalse(can_monitor(self.scoped))
        user = get_user_model().objects.create_user(
            username="auditor", user_type="operador"
        )
        user.user_permissions.add(permission)
        self.assertTrue(can_monitor(user))
        self.client.force_login(user)
        self.assertEqual(
            self.client.get(reverse("observability:rules")).status_code, 403
        )

    @override_settings(MONITOR_METRICS_TOKEN="test-secret-token")
    def test_private_metrics_and_bounded_labels(self):
        url = reverse("observability:metrics")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(url, HTTP_AUTHORIZATION="Bearer wrong").status_code, 403
        )
        response = self.client.get(url, HTTP_AUTHORIZATION="Bearer test-secret-token")
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertNotIn("test-secret-token", text)
        self.assertNotIn(self.user.username, text)
        families = list(text_string_to_metric_families(text))
        self.assertTrue(any(f.name == "bonanza_support_tickets" for f in families))
        forbidden = {"user", "user_id", "username", "ticket", "ticket_id", "ip", "path"}
        for family in families:
            for sample in family.samples:
                self.assertFalse(forbidden.intersection(sample.labels))
        self.assertEqual(self.client.post(url).status_code, 405)

    @override_settings(GRAFANA_URL="https://grafana.example.test")
    def test_grafana_uses_fixed_authenticated_dashboard_links(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("observability:grafana", args=["general"]))
        self.assertEqual(response.url, "https://grafana.example.test/d/bonanza-general")
        self.assertEqual(
            self.client.get(
                reverse("observability:grafana", args=["unknown"])
            ).status_code,
            404,
        )
        with override_settings(GRAFANA_URL="https://name:secret@grafana.example.test"):
            self.assertEqual(
                self.client.get(
                    reverse("observability:grafana", args=["general"])
                ).status_code,
                404,
            )

    def test_activity_sample_is_temporal_and_throttled(self):
        _seen.clear()
        record_activity(self.user)
        self.assertTrue(UserActivity.objects.filter(user=self.user).exists())
        with CaptureQueriesContext(connection) as queries:
            record_activity(self.user)
        self.assertEqual(len(queries), 0)
        UserActivity.objects.filter(user=self.user).update(
            last_seen=timezone.now() - timedelta(hours=1)
        )
        data = snapshot(force=True)
        self.assertEqual(data["users"]["active"], 0)
        self.assertEqual(data["database_vendor"], "sqlite")
        self.assertNotIn("database_connections", data)

    def test_snapshot_cache_avoids_repeating_aggregate_queries(self):
        snapshot(force=True)
        with CaptureQueriesContext(connection) as queries:
            snapshot()
        self.assertEqual(len(queries), 0)

    def test_rules_persist_audit_and_require_admin(self):
        self.client.force_login(self.admin)
        rule = AlertRule.objects.first()
        response = self.client.post(
            reverse("observability:rules"),
            {
                "pk": rule.pk,
                f"{rule.pk}-threshold": "92",
                f"{rule.pk}-hold_seconds": "60",
                f"{rule.pk}-severity": "warning",
                f"{rule.pk}-enabled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        rule.refresh_from_db()
        self.assertEqual(rule.threshold, 92)
        self.assertTrue(
            SupportAudit.objects.filter(action="monitor_rule_changed").exists()
        )

    def test_alert_hold_dedup_resolution_and_unknown(self):
        rule = AlertRule.objects.create(
            name="Test rule", signal="cpu", threshold=80, hold_seconds=60
        )
        now = timezone.now()
        evaluate({"cpu": 90}, now)
        item = AlertIncident.objects.get(rule=rule)
        self.assertIsNone(item.detected_at)
        evaluate({"cpu": 90}, now + timedelta(seconds=61))
        evaluate({"cpu": 90}, now + timedelta(seconds=90))
        self.assertEqual(AlertIncident.objects.filter(rule=rule).count(), 1)
        self.assertEqual(
            AlertEvent.objects.filter(incident=item, kind="firing").count(), 1
        )
        evaluate({"cpu": None}, now + timedelta(seconds=100))
        item.refresh_from_db()
        self.assertIsNone(item.resolved_at)
        evaluate({"cpu": 20}, now + timedelta(seconds=120))
        item.refresh_from_db()
        self.assertIsNotNone(item.resolved_at)
        self.assertEqual(
            AlertEvent.objects.filter(incident=item, kind="resolved").count(), 1
        )

    def test_sampler_does_not_send_external_notifications(self):
        from django.core.management import call_command

        with (
            patch("requests.post") as post,
            patch("django.core.mail.send_mail") as mail,
        ):
            call_command("sample_monitoring", verbosity=0)
        post.assert_not_called()
        mail.assert_not_called()

    def test_authentication_failure_increments_aggregate_metric(self):
        from .metrics import AUTH_FAILURES

        before = AUTH_FAILURES._value.get()
        self.client.post(
            reverse("login"), {"username": "invalid-user", "password": "DO-NOT-EXPOSE"}
        )
        self.assertEqual(AUTH_FAILURES._value.get(), before + 1)

    def test_database_query_instrumentation_records_errors_without_sql_labels(self):
        from django.db import OperationalError

        from .metrics import DB_ERRORS
        from .middleware import measure_sql

        before = DB_ERRORS._value.get()

        def fail(*args):
            raise OperationalError("sample")

        with self.assertRaises(OperationalError):
            measure_sql(fail, "SELECT secret FROM confidential", [], False, {})
        self.assertEqual(DB_ERRORS._value.get(), before + 1)


class InstrumentationCostTests(SimpleTestCase):
    def request(self):
        request = RequestFactory().get("/soporte/")
        request.user = AnonymousUser()
        return request

    @override_settings(OBSERVABILITY_ENABLED=True)
    def test_instrumentation_has_no_database_queries_for_anonymous_empty_view(self):
        middleware = MetricsMiddleware(lambda request: HttpResponse("ok"))
        # SimpleTestCase forbids DB access: instrumenting a view must not create SQL.
        for _ in range(10):
            self.assertEqual(middleware(self.request()).status_code, 200)

    @override_settings(OBSERVABILITY_ENABLED=True)
    def test_parallel_requests_have_consistent_counters(self):
        from .metrics import INFLIGHT, REQUESTS

        counter = REQUESTS.labels("support:list", "GET", "200")
        before = counter._value.get()
        middleware = MetricsMiddleware(lambda request: HttpResponse("ok"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(
                pool.map(lambda _: middleware(self.request()).status_code, range(200))
            )
        self.assertEqual(statuses, [200] * 200)
        self.assertEqual(counter._value.get() - before, 200)
        self.assertEqual(INFLIGHT._value.get(), 0)

    def test_disabled_mode_and_small_bounded_instrumentation_cost(self):
        request = self.request()
        middleware = MetricsMiddleware(lambda request: HttpResponse("ok"))
        costs = {}
        for enabled in (False, True):
            with override_settings(OBSERVABILITY_ENABLED=enabled):
                started = time.perf_counter()
                for _ in range(1000):
                    middleware(request)
                costs[enabled] = (time.perf_counter() - started) / 1000
        # Loose CI bound, not a production capacity guarantee. No load on production.
        self.assertLess(costs[True] - costs[False], 0.002)
        print(
            f"Instrumentation benchmark: baseline={costs[False] * 1e6:.1f}us enabled={costs[True] * 1e6:.1f}us per request"
        )

    def test_multiprocess_counters_and_dead_worker_cleanup(self):
        from prometheus_client import CollectorRegistry, multiprocess

        script = """from prometheus_client import Counter,Gauge
c=Counter('test_bonanza_requests_total','test');c.inc(3)
g=Gauge('test_bonanza_workers','test',multiprocess_mode='livesum');g.set(1)
"""
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, PROMETHEUS_MULTIPROC_DIR=directory)
            workers = [
                subprocess.Popen([sys.executable, "-c", script], env=environment)
                for _ in range(2)
            ]
            for worker in workers:
                self.assertEqual(worker.wait(timeout=10), 0)
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry, path=directory)
            self.assertEqual(
                registry.get_sample_value("test_bonanza_requests_total"), 6
            )
            self.assertEqual(registry.get_sample_value("test_bonanza_workers"), 2)
            for worker in workers:
                multiprocess.mark_process_dead(worker.pid, path=directory)
            self.assertIsNone(registry.get_sample_value("test_bonanza_workers"))


class PerServiceAlertTests(TestCase):
    def test_incidents_identify_affected_service_and_do_not_duplicate(self):
        rule = AlertRule.objects.create(
            name="Servicios de prueba",
            signal="service_down",
            threshold=0,
            hold_seconds=0,
        )
        evaluate({}, service_values={"minio": 1, "people_api": 0})
        evaluate({}, service_values={"minio": 1, "people_api": 0})
        incident = AlertIncident.objects.get(rule=rule)
        self.assertEqual(incident.service, "minio")
        self.assertEqual(incident.events.filter(kind="firing").count(), 1)
        evaluate({}, service_values={"minio": 0})
        incident.refresh_from_db()
        self.assertIsNotNone(incident.resolved_at)

    def test_disabling_rule_resolves_service_incidents_even_without_telemetry(self):
        rule = AlertRule.objects.create(
            name="Deshabilitada", signal="service_down", threshold=0, hold_seconds=0
        )
        evaluate({}, service_values={"minio": 1})
        rule.enabled = False
        rule.save()
        evaluate({})
        item = AlertIncident.objects.get(rule=rule)
        self.assertIsNotNone(item.resolved_at)
        self.assertTrue(item.events.filter(kind="disabled").exists())


class NewModuleTemplateTests(SimpleTestCase):
    def test_all_new_templates_compile(self):
        from pathlib import Path

        from django.conf import settings
        from django.template.loader import get_template

        for app in ("support", "observability"):
            root = Path(settings.BASE_DIR) / app / "templates"
            for path in root.rglob("*.html"):
                with self.subTest(template=str(path.relative_to(root))):
                    get_template(str(path.relative_to(root)))


@override_settings(SECURE_SSL_REDIRECT=False)
class ReportedTicketsDashboardTests(TestCase):
    def test_robiotec_profile_sees_reports_from_all_organizations(self):
        from support.models import Category
        from support.services import create_ticket

        User = get_user_model()
        admin = User.objects.create_user(
            username="robiotec", user_type="global_admin", is_superuser=True
        )
        for number in range(2):
            organization = Organization.objects.create(
                name=f"Reportes {number}", slug=f"reports-{number}"
            )
            user = User.objects.create_user(
                username=f"reporter-{number}", user_type="rh", organization=organization
            )
            create_ticket(
                user,
                {
                    "subject": f"Reporte visible {number}",
                    "description": "Solicitud de un usuario",
                    "category": Category.objects.first(),
                },
            )
            self.client.force_login(user)
            response = self.client.get(reverse("support:list"))
            self.assertContains(response, "Mesa de ayuda")
            self.assertNotContains(response, "Centro de monitoreo")
            self.assertContains(response, f"Reporte visible {number}")
            self.assertNotContains(response, f"Reporte visible {1 - number}")
        self.client.force_login(admin)
        import observability.snapshot as snapshots

        snapshots._cached = None
        response = self.client.get(reverse("observability:dashboard"))
        self.assertContains(response, "Reportes recientes de los usuarios")
        for number in range(2):
            self.assertContains(response, f"Reporte visible {number}")
        self.assertContains(response, reverse("support:list") + "?team=1")

    def test_monitoring_permission_alone_does_not_expose_ticket_subjects(self):
        from support.models import Category
        from support.services import create_ticket

        User = get_user_model()
        user = User.objects.create_user(username="reporter-private", user_type="rh")
        create_ticket(
            user,
            {
                "subject": "ASUNTO_RESERVADO_DE_SOPORTE",
                "description": "Solicitud privada",
                "category": Category.objects.first(),
            },
        )
        observer = User.objects.create_user(
            username="technical-observer", user_type="operador"
        )
        observer.user_permissions.add(
            Permission.objects.get(
                codename="view_monitoring", content_type__app_label="observability"
            )
        )
        self.client.force_login(observer)
        import observability.snapshot as snapshots

        snapshots._cached = None
        response = self.client.get(reverse("observability:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "ASUNTO_RESERVADO_DE_SOPORTE")
        self.assertNotContains(response, "Reportes recientes de los usuarios")


@override_settings(SECURE_SSL_REDIRECT=False)
class GrafanaProxyAuthorizationTests(TestCase):
    def test_authentication_and_roles_cannot_be_forged_with_headers(self):
        url = reverse("observability:grafana_access")
        self.assertEqual(
            self.client.get(url, HTTP_X_WEBAUTH_USER="robiotec").status_code, 401
        )
        user = get_user_model().objects.create_user(
            username="non-admin-proxy", user_type="rh"
        )
        self.client.force_login(user)
        self.assertEqual(
            self.client.get(url, HTTP_X_WEBAUTH_ROLE="Admin").status_code, 403
        )
        admin = get_user_model().objects.create_user(
            username="robiotec", user_type="global_admin"
        )
        self.client.force_login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["X-Grafana-User"], "robiotec")
        self.assertEqual(response["X-Grafana-Role"], "Admin")
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_explicit_observer_receives_viewer_role(self):
        user = get_user_model().objects.create_user(
            username="proxy-observer", user_type="operador"
        )
        user.user_permissions.add(
            Permission.objects.get(
                codename="view_monitoring", content_type__app_label="observability"
            )
        )
        self.client.force_login(user)
        response = self.client.get(reverse("observability:grafana_access"))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["X-Grafana-Role"], "Viewer")
