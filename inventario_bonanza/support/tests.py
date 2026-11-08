import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from gestion_personal.models import Organization

from .forms import TicketForm, validate_attachment
from .models import (
    Attachment,
    Category,
    Comment,
    Notification,
    Priority,
    SLAPolicy,
    Status,
    SupportAudit,
    Ticket,
    TicketEvent,
)
from .services import Conflict, add_comment, create_ticket, update_ticket
from .storage import PrivateSupportStorage


@override_settings(SECURE_SSL_REDIRECT=False)
class SupportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.org = Organization.objects.create(name="Support A", slug="support-a")
        cls.other_org = Organization.objects.create(name="Support B", slug="support-b")
        cls.user = User.objects.create_user(
            username="support-user", user_type="rh", organization=cls.org
        )
        cls.other = User.objects.create_user(
            username="support-other", user_type="rh", organization=cls.org
        )
        cls.foreign = User.objects.create_user(
            username="support-foreign", user_type="rh", organization=cls.other_org
        )
        cls.admin = User.objects.create_user(
            username="support-admin", user_type="global_admin"
        )
        cls.agent = User.objects.create_user(
            username="support-agent", user_type="operador", organization=cls.org
        )
        cls.agent.groups.add(Group.objects.get(name="Agentes de soporte"))
        cls.foreign_agent = User.objects.create_user(
            username="foreign-agent", user_type="operador", organization=cls.other_org
        )
        cls.foreign_agent.groups.add(Group.objects.get(name="Agentes de soporte"))
        cls.category = Category.objects.first()
        cls.ticket = create_ticket(
            cls.user,
            {
                "subject": "Acceso a reporte",
                "description": "No aparece el reporte.",
                "category": cls.category,
            },
        )

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, ticket=None, **kwargs):
        ticket = ticket or self.ticket
        return {
            "version": ticket.version,
            "status": ticket.status,
            "priority": ticket.priority,
            **kwargs,
        }

    def test_create_and_personal_history(self):
        response = self.client.post(
            reverse("support:create"),
            {
                "subject": "Nueva solicitud",
                "description": "Descripción",
                "category": self.category.pk,
                "priority": "critical",
                "requester": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get(subject="Nueva solicitud")
        self.assertEqual(ticket.requester, self.user)
        self.assertEqual(ticket.organization, self.org)
        self.assertEqual(ticket.priority, Priority.MEDIUM)
        self.assertEqual(ticket.events.count(), 1)
        self.assertContains(self.client.get(reverse("support:list")), "Nueva solicitud")

    def test_inactive_category_rejected(self):
        self.category.active = False
        self.category.save()
        form = TicketForm(
            {"subject": "Test", "description": "Text", "category": self.category.pk}
        )
        self.assertFalse(form.is_valid())

    def test_other_user_cannot_read_or_comment(self):
        for user in (self.other, self.foreign, self.foreign_agent):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(
                    reverse("support:detail", args=[self.ticket.pk])
                ).status_code,
                404,
            )
            response = self.client.post(
                reverse("support:detail", args=[self.ticket.pk]),
                {"action": "comment", "version": 0, "body": "Intrusión"},
            )
            self.assertEqual(response.status_code, 404)
        self.assertFalse(Comment.objects.exists())

    def test_regular_users_cannot_open_team_or_statistics_or_config(self):
        for url in [
            reverse("support:list") + "?team=1",
            reverse("support:dashboard"),
            reverse("support:configuration"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_agent_only_sees_assigned_ticket(self):
        self.client.force_login(self.agent)
        self.assertEqual(
            self.client.get(
                reverse("support:detail", args=[self.ticket.pk])
            ).status_code,
            404,
        )
        ticket = update_ticket(self.admin, self.ticket, self.data(assignee=self.agent))
        self.assertEqual(
            self.client.get(reverse("support:detail", args=[ticket.pk])).status_code,
            200,
        )
        self.assertContains(
            self.client.get(reverse("support:list") + "?team=1"), ticket.subject
        )

    def test_cannot_assign_foreign_agent(self):
        with self.assertRaises(ValidationError):
            update_ticket(
                self.admin, self.ticket, self.data(assignee=self.foreign_agent)
            )
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assignee)
        self.assertEqual(self.ticket.version, 0)

    def test_priority_is_controlled_by_support(self):
        with self.assertRaises(PermissionDenied):
            update_ticket(self.user, self.ticket, self.data(priority=Priority.CRITICAL))
        ticket = update_ticket(
            self.admin, self.ticket, self.data(priority=Priority.HIGH)
        )
        self.assertEqual(ticket.priority, Priority.HIGH)
        self.assertTrue(ticket.events.filter(kind="priority").exists())

    def test_full_workflow_confirmation_and_reopening(self):
        ticket = update_ticket(self.admin, self.ticket, self.data(status=Status.REVIEW))
        ticket = update_ticket(
            self.admin, ticket, self.data(ticket, status=Status.PROGRESS)
        )
        ticket = update_ticket(
            self.admin, ticket, self.data(ticket, status=Status.WAITING)
        )
        ticket = update_ticket(
            self.admin, ticket, self.data(ticket, status=Status.RESOLVED)
        )
        self.assertIsNotNone(ticket.resolved_at)
        ticket = update_ticket(
            self.user,
            ticket,
            self.data(ticket, status=Status.CLOSED),
            requester_action=True,
        )
        self.assertIsNotNone(ticket.closed_at)
        ticket = update_ticket(
            self.user,
            ticket,
            self.data(ticket, status=Status.OPEN),
            requester_action=True,
        )
        self.assertIsNone(ticket.resolved_at)
        self.assertEqual(ticket.status, Status.OPEN)

    def test_invalid_transition_and_unresolved_confirmation(self):
        with self.assertRaises(ValidationError):
            update_ticket(self.admin, self.ticket, self.data(status=Status.CLOSED))
        with self.assertRaises(ValidationError):
            update_ticket(
                self.user,
                self.ticket,
                self.data(status=Status.CLOSED),
                requester_action=True,
            )

    def test_expired_reopening(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(
            status=Status.RESOLVED, resolved_at=timezone.now() - timedelta(days=8)
        )
        self.ticket.refresh_from_db()
        with self.assertRaises(ValidationError):
            update_ticket(
                self.user,
                self.ticket,
                self.data(status=Status.OPEN),
                requester_action=True,
            )

    def test_stale_updates_are_rejected_without_duplicate_events(self):
        original = self.ticket.version
        update_ticket(self.admin, self.ticket, self.data(status=Status.REVIEW))
        with self.assertRaises(Conflict):
            update_ticket(
                self.admin,
                self.ticket,
                {"version": original, "status": Status.PROGRESS},
            )
        self.assertEqual(
            TicketEvent.objects.filter(ticket=self.ticket, kind="status").count(), 1
        )

    def test_internal_notes_and_attachments_are_private(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(SUPPORT_PRIVATE_ROOT=directory),
        ):
            field = Attachment._meta.get_field("file")
            old = field.storage
            field.storage = PrivateSupportStorage()
            try:
                ticket = update_ticket(
                    self.admin, self.ticket, self.data(assignee=self.agent)
                )
                upload = SimpleUploadedFile(
                    "nota.txt", b"contenido privado", content_type="text/plain"
                )
                ticket = add_comment(
                    self.agent,
                    ticket,
                    {
                        "version": ticket.version,
                        "body": "NOTA_INTERNA_SECRETA",
                        "internal": True,
                        "attachment": upload,
                    },
                )
                attachment = ticket.attachments.get()
                self.assertEqual(
                    self.client.get(
                        reverse("support:download", args=[attachment.pk])
                    ).status_code,
                    404,
                )
                page = self.client.get(reverse("support:detail", args=[ticket.pk]))
                self.assertNotContains(page, "NOTA_INTERNA_SECRETA")
                self.assertNotContains(page, "nota.txt")
                self.client.force_login(self.agent)
                self.assertContains(
                    self.client.get(reverse("support:detail", args=[ticket.pk])),
                    "NOTA_INTERNA_SECRETA",
                )
                self.assertEqual(
                    self.client.get(
                        reverse("support:download", args=[attachment.pk])
                    ).status_code,
                    200,
                )
                with self.assertRaises(ValueError):
                    _ = attachment.file.url
                self.assertEqual(
                    Path(attachment.file.path).stat().st_mode & 0o777, 0o600
                )
            finally:
                field.storage = old

    def test_public_reply_sets_first_response_and_notifies(self):
        ticket = add_comment(
            self.admin, self.ticket, {"version": 0, "body": "Respuesta pública"}
        )
        self.assertIsNotNone(ticket.first_response_at)
        self.assertTrue(
            Notification.objects.filter(recipient=self.user, ticket=ticket).exists()
        )
        self.assertContains(
            self.client.get(reverse("support:notifications")), "Nueva respuesta"
        )
        note = Notification.objects.filter(recipient=self.user).first()
        self.assertEqual(
            self.client.get(
                reverse("support:read_notification", args=[note.pk])
            ).status_code,
            405,
        )
        self.client.post(reverse("support:read_notification", args=[note.pk]))
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)

    def test_internal_reply_does_not_count_as_first_response_or_notify_user(self):
        ticket = add_comment(
            self.admin,
            self.ticket,
            {"version": 0, "body": "Solo equipo", "internal": True},
        )
        self.assertIsNone(ticket.first_response_at)
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())

    def test_customer_cannot_submit_internal_note_via_service(self):
        with self.assertRaises(PermissionDenied):
            add_comment(
                self.user,
                self.ticket,
                {"version": 0, "body": "Intento", "internal": True},
            )

    def test_valid_and_invalid_uploads(self):
        for name, body in [
            ("x.svg", b"<svg/>"),
            ("x.exe", b"MZ"),
            ("x.png", b"not image"),
            ("x.txt", b"\0binary"),
        ]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_attachment(SimpleUploadedFile(name, body))
        for name, body in [
            ("x.png", b"\x89PNG\r\n\x1a\nimage"),
            ("x.jpg", b"\xff\xd8\xffimage"),
            ("x.pdf", b"%PDF-1.7\n"),
            ("x.txt", b"texto"),
        ]:
            with self.subTest(name=name):
                self.assertTrue(validate_attachment(SimpleUploadedFile(name, body)))
        with (
            override_settings(SUPPORT_MAX_UPLOAD_BYTES=4),
            self.assertRaises(ValidationError),
        ):
            validate_attachment(SimpleUploadedFile("x.txt", b"12345"))

    def test_public_upload_download_and_cross_user_denial(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            override_settings(SUPPORT_PRIVATE_ROOT=directory),
        ):
            field = Attachment._meta.get_field("file")
            old = field.storage
            field.storage = PrivateSupportStorage()
            try:
                form = TicketForm(
                    {
                        "subject": "Archivo",
                        "description": "Texto",
                        "category": self.category.pk,
                    },
                    {"attachment": SimpleUploadedFile("captura.txt", b"hola")},
                )
                self.assertTrue(form.is_valid(), form.errors)
                ticket = create_ticket(self.user, form.cleaned_data)
                item = ticket.attachments.get()
                response = self.client.get(reverse("support:download", args=[item.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertIn("attachment", response["Content-Disposition"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                response.close()
                self.client.force_login(self.other)
                self.assertEqual(
                    self.client.get(
                        reverse("support:download", args=[item.pk])
                    ).status_code,
                    404,
                )
            finally:
                field.storage = old

    def test_sla_configured_and_overdue(self):
        policy = SLAPolicy.objects.get(priority=Priority.MEDIUM)
        policy.enabled = True
        policy.save()
        ticket = create_ticket(
            self.user,
            {"subject": "SLA", "description": "Demo", "category": self.category},
        )
        self.assertEqual(
            ticket.resolution_due_at - ticket.created_at, timedelta(hours=72)
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            resolution_due_at=timezone.now() - timedelta(seconds=1)
        )
        ticket.refresh_from_db()
        self.assertTrue(ticket.overdue)
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get(reverse("support:list") + "?team=1&overdue=on"), "SLA"
        )

    def test_filters_stats_and_pagination(self):
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get(reverse("support:dashboard")), "Estadísticas de atención"
        )
        self.assertContains(
            self.client.get(
                reverse("support:list") + "?team=1&q=" + str(self.ticket.pk)
            ),
            self.ticket.subject,
        )
        self.assertNotContains(
            self.client.get(reverse("support:list") + "?team=1&priority=critical"),
            self.ticket.subject,
        )
        self.assertEqual(
            self.client.get(
                reverse("support:dashboard") + "?start=2026-11-08&end=2026-01-01"
            ).status_code,
            200,
        )

    def test_configuration_and_permission_audit(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("support:configuration")).status_code, 200
        )
        response = self.client.post(
            reverse("support:configuration"),
            {"kind": "agent", "user": self.other.pk, "enabled": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.other.groups.filter(name="Agentes de soporte").exists())
        self.assertTrue(
            SupportAudit.objects.filter(action="agent_permission_changed").exists()
        )
        self.client.post(
            reverse("support:configuration"),
            {"kind": "category", "name": "Nueva categoría", "active": "on"},
        )
        self.assertTrue(
            Category.objects.filter(name="Nueva categoría", active=True).exists()
        )

    def test_unauthenticated_and_csrf_protection(self):
        from django.test import Client

        anonymous = Client()
        self.assertEqual(anonymous.get(reverse("support:list")).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(
            strict.post(reverse("support:create"), {"subject": "csrf"}).status_code, 403
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class ConcurrentTicketTests(TransactionTestCase):
    def test_two_simultaneous_comments_do_not_overwrite_each_other(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import OperationalError, connections

        user = get_user_model().objects.create_user(
            username="concurrent-ticket-user", user_type="rh"
        )
        user.get_all_permissions()
        category = Category.objects.first() or Category.objects.create(
            name="Prueba concurrente"
        )
        ticket = create_ticket(
            user,
            {"subject": "Concurrente", "description": "Prueba", "category": category},
        )
        barrier = Barrier(2)

        def write(index):
            connections.close_all()
            barrier.wait(timeout=5)
            try:
                add_comment(user, ticket, {"version": 0, "body": f"Respuesta {index}"})
                return "saved"
            except (Conflict, OperationalError):
                return "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, range(2)))
        self.assertEqual(sorted(results), ["conflict", "saved"])
        self.assertEqual(ticket.comments.count(), 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.version, 1)
