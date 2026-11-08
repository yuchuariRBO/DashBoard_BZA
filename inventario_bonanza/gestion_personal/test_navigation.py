from datetime import date
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import CustomUser, Organization, Person
from .services.roles import DASHBOARD_BY_ROLE


@override_settings(SECURE_SSL_REDIRECT=False)
class ProfileNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Auditoría', slug='audit')
        cls.person = Person.objects.create(first_name='Prueba', last_name='Auditoria', id_number='0102030405', birth_date=date(1990, 1, 1), gender='F', organization=cls.organization)
        cls.users = []
        for role in DASHBOARD_BY_ROLE:
            cls.users.append(CustomUser.objects.create_user(username='audit-' + role, user_type=role, organization=None if role == 'global_admin' else cls.organization))
        cls.users.append(CustomUser.objects.create_user(username='audit-scoped-admin', user_type='global_admin', organization=cls.organization))

    def test_dashboard_and_each_visible_sidebar_link(self):
        for user in self.users:
            self.client.force_login(user)
            with self.subTest(user=user.username, page='dashboard'):
                response = self.client.get(reverse(DASHBOARD_BY_ROLE[user.user_type]))
                self.assertEqual(response.status_code, 200)
                soup = BeautifulSoup(response.content, 'html.parser')
                links = {a.get('href') for a in soup.select('aside a[href]')}
                self.assertTrue(links)
            for link in links:
                if not link or not link.startswith('/') or urlsplit(link).path == '/logout/':
                    continue
                with self.subTest(user=user.username, link=link):
                    page = self.client.get(link)
                    self.assertEqual(page.status_code, 200)

    def test_each_role_redirects_to_its_dashboard(self):
        for user in self.users:
            self.client.force_login(user)
            with self.subTest(user=user.username):
                response = self.client.get(reverse('role_based_redirect'))
                self.assertEqual(response.url, reverse(DASHBOARD_BY_ROLE[user.user_type]))

    def test_dashboard_access_is_restricted_by_role(self):
        for user in self.users:
            self.client.force_login(user)
            for role, view in DASHBOARD_BY_ROLE.items():
                if view == DASHBOARD_BY_ROLE[user.user_type] or (user.user_type == 'global_admin' and user.organization_id and view == 'dashboard_rrhh'):
                    continue
                with self.subTest(user=user.username, view=view):
                    self.assertIn(self.client.get(reverse(view)).status_code, (302, 403))


@override_settings(SECURE_SSL_REDIRECT=False)
class SecondaryRouteAuditTests(ProfileNavigationTests):
    def test_static_routes_do_not_crash(self):
        from .urls import urlpatterns
        for user in self.users:
            self.client.force_login(user)
            for pattern in urlpatterns:
                route = str(pattern.pattern)
                if '<' in route or not pattern.name:
                    continue
                with self.subTest(user=user.username, route=route):
                    response = self.client.get(reverse(pattern.name))
                    self.assertLess(response.status_code, 500)


@override_settings(SECURE_SSL_REDIRECT=False)
class AuditOrganizationIsolationTests(TestCase):
    def test_operator_cannot_exit_another_organizations_vehicle(self):
        from .models import VehicleRecord
        first = Organization.objects.create(name='Vehicles A', slug='vehicles-a')
        second = Organization.objects.create(name='Vehicles B', slug='vehicles-b')
        operator = CustomUser.objects.create_user(username='operator-a', user_type='operador', organization=first)
        vehicle = VehicleRecord.objects.create(placa='ABC1234', organization=second)
        self.client.force_login(operator)
        response = self.client.post(reverse('vehicle_exit'), {'vehicle_id': vehicle.pk})
        self.assertEqual(response.status_code, 404)
        vehicle.refresh_from_db()
        self.assertIsNone(vehicle.fecha_salida)
        vehicle.organization = first
        vehicle.save()
        self.assertEqual(self.client.post(reverse('vehicle_exit'), {'vehicle_id': vehicle.pk}).status_code, 302)
        vehicle.refresh_from_db()
        self.assertIsNotNone(vehicle.fecha_salida)

    def test_epp_person_selector_is_organization_scoped(self):
        from .forms import EPPAssignmentForm
        first = Organization.objects.create(name='EPP A', slug='epp-a')
        second = Organization.objects.create(name='EPP B', slug='epp-b')
        technician = CustomUser.objects.create_user(username='technician-a', user_type='tecnico_seguridad', organization=first)
        own = Person.objects.create(first_name='Own', last_name='Person', id_number='0102030405', birth_date=date(1990, 1, 1), gender='F', organization=first)
        other = Person.objects.create(first_name='Other', last_name='Person', id_number='1111111111', birth_date=date(1990, 1, 1), gender='M', organization=second)
        form = EPPAssignmentForm(asignado_por=technician)
        self.assertEqual(list(form.fields['person'].queryset), [own])
        forged = EPPAssignmentForm({'person': other.pk, 'tipo_epp': 'casco'}, asignado_por=technician)
        self.assertFalse(forged.is_valid())
        self.assertIn('person', forged.errors)
