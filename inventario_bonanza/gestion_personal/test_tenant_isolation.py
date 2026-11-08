from datetime import date
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.urls import reverse
from .models import CustomUser, Organization, VisitorRecord, VisitaProgramada, PlateLookupRecord, PersonLookupRecord
from .services.scoping import organization_records_for


@override_settings(SECURE_SSL_REDIRECT=False)
class TenantIsolationTests(TestCase):
    def setUp(self):
        self.a = Organization.objects.create(name='Tenant A', slug='tenant-a')
        self.b = Organization.objects.create(name='Tenant B', slug='tenant-b')
        self.guard = CustomUser.objects.create_user(username='guard-a', user_type='seguridad_fisica', organization=self.a, email='guard-a@example.com')
        self.other_guard = CustomUser.objects.create_user(username='guard-b', user_type='seguridad_fisica', organization=self.b, email='guard-b@example.com')
        self.operator = CustomUser.objects.create_user(username='operator-tenant-a', user_type='operador', organization=self.a)
        self.client.force_login(self.guard)

    def make_visit(self, org, user):
        return VisitaProgramada.objects.create(organization=org, nombre='Visit ' + org.slug, identificacion='0102030405', motivo='Test', fecha_programada=date.today(), hora_programada='10:00', area_visita='Mina', autorizado_por='Seguridad', programado_por=user)

    @patch('gestion_personal.models.send_email_notification')
    def test_visitor_lists_creation_exit_and_notification_are_scoped(self, notify):
        own = VisitorRecord.objects.create(organization=self.a, nombre='Own Visitor', cedula='0102030405', area_visita='Mina', autorizado_por='Seguridad')
        other = VisitorRecord.objects.create(organization=self.b, nombre='Secret Visitor', cedula='1111111111', area_visita='Mina', autorizado_por='Seguridad')
        for view in ('dashboard_seguridad', 'registros_por_fecha'):
            response = self.client.get(reverse(view))
            self.assertContains(response, 'Own Visitor')
            self.assertNotContains(response, 'Secret Visitor')
        self.client.force_login(self.operator)
        self.client.post(reverse('visitor_exit'), {'visitante_id': other.pk})
        other.refresh_from_db()
        self.assertIsNone(other.fecha_salida)
        self.client.post(reverse('visitor_exit'), {'visitante_id': own.pk})
        own.refresh_from_db()
        self.assertIsNotNone(own.fecha_salida)
        notify.reset_mock()
        self.client.post(reverse('visitor_create'), {'nombre': 'New Visitor', 'cedula': '2222222222', 'area_visita': 'Mina', 'autorizado_por': 'Seguridad', 'organization': self.b.pk})
        self.assertEqual(VisitorRecord.objects.get(nombre='New Visitor').organization, self.a)
        self.assertEqual(notify.call_args.args[2], ['guard-a@example.com'])

    @patch('gestion_personal.models.send_email_notification')
    def test_foreign_scheduled_visit_cannot_be_completed_or_linked(self, notify):
        foreign = self.make_visit(self.b, self.other_guard)
        own = self.make_visit(self.a, self.guard)
        self.client.force_login(self.operator)
        page = self.client.get(reverse('dashboard_operador'))
        self.assertNotContains(page, foreign.nombre)
        self.assertContains(page, own.nombre)
        self.assertEqual(self.client.post(reverse('completar_visita_programada', args=[foreign.pk])).status_code, 404)
        response = self.client.post(reverse('visitor_create'), {'nombre': 'Forged', 'cedula': '2222222222', 'area_visita': 'Mina', 'autorizado_por': 'Seguridad', 'visita_programada_id': foreign.pk})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(VisitorRecord.objects.exists())
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, 'pendiente')
        self.assertEqual(self.client.post(reverse('completar_visita_programada', args=[own.pk])).status_code, 200)
        self.assertEqual(VisitorRecord.objects.get().organization, self.a)
        self.assertEqual(self.client.post(reverse('completar_visita_programada', args=[own.pk])).status_code, 404)

    def test_foreign_visit_cannot_be_edited_or_cancelled(self):
        visit = self.make_visit(self.b, self.other_guard)
        for view in ('editar_visita_programada', 'cancelar_visita_programada'):
            self.assertEqual(self.client.post(reverse(view, args=[visit.pk]), {}).status_code, 404)
        visit.refresh_from_db()
        self.assertEqual(visit.status, 'pendiente')

    @patch('gestion_personal.models.send_email_notification')
    def test_legacy_unassigned_visitors_are_quarantined(self, notify):
        legacy = VisitorRecord.objects.create(nombre='Legacy', cedula='1234567890', area_visita='Mina', autorizado_por='Unknown')
        self.assertFalse(organization_records_for(VisitorRecord, self.guard).filter(pk=legacy.pk).exists())
        self.guard.organization = None
        self.assertFalse(organization_records_for(VisitorRecord, self.guard).exists())
        notify.assert_not_called()


    @patch('gestion_personal.views.start_person_lookup_process', return_value=True)
    @patch('gestion_personal.views.start_plate_lookup_process', return_value=True)
    def test_lookup_cache_is_shared_between_organizations(self, plate_start, person_start):
        for model, field, value, view in ((PersonLookupRecord, 'cedula', '0102030405', 'global_person_lookup'), (PlateLookupRecord, 'placa', 'ABC1234', 'global_plate_lookup')):
            shared = model.objects.create(consultado_por=self.other_guard, **{field: value}, lookup_status='completed')
            response = self.client.get(reverse(view), {field: value, 'tab': 'base'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['record'], shared)
            self.assertEqual(response.context['db_page'].paginator.count, 1)

    @patch('gestion_personal.management.commands.lookup_person.consultar_persona_completa')
    def test_external_result_updates_shared_local_record(self, source):
        record = PersonLookupRecord.objects.create(cedula='0102030405', consultado_por=self.guard)
        source.return_value = {'cedula': '0102030405', 'normalized': {'nombre_completo': 'Shared Result', 'procesos_actor_total': 0, 'procesos_demandado_total': 0, 'citaciones_total': 0}, 'sources': {}, 'errors': {}}
        call_command('lookup_person', '0102030405', record_id=record.pk)
        self.client.force_login(self.other_guard)
        response = self.client.get(reverse('global_person_lookup'), {'cedula': '0102030405'})
        self.assertEqual(response.context['record'].nombre_completo, 'Shared Result')
        self.assertEqual(PersonLookupRecord.objects.count(), 1)

    def test_visit_organization_does_not_follow_creator_transfer(self):
        visit = self.make_visit(self.b, self.other_guard)
        self.other_guard.organization = self.a
        self.other_guard.save()
        self.client.force_login(self.other_guard)
        self.assertEqual(self.client.post(reverse('cancelar_visita_programada', args=[visit.pk])).status_code, 404)
        visit.refresh_from_db()
        self.assertEqual(visit.organization, self.b)

    @patch('gestion_personal.management.commands.send_daily_report.EmailMessage')
    def test_daily_report_goes_only_to_system_admins(self, email):
        CustomUser.objects.create_user(username='report-system', user_type='global_admin', email='system@example.com')
        CustomUser.objects.create_user(username='report-tenant', user_type='global_admin', organization=self.a, email='tenant@example.com')
        call_command('send_daily_report')
        self.assertEqual(email.call_args.kwargs['to'], ['system@example.com'])
