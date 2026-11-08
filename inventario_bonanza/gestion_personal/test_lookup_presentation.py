from django.test import TestCase, override_settings
from django.urls import reverse
from .models import CustomUser, PersonLookupRecord


@override_settings(SECURE_SSL_REDIRECT=False)
class PersonLookupPresentationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='presentation-test', user_type='global_admin')
        self.client.force_login(self.user)
        self.record = PersonLookupRecord.objects.create(
            cedula='0000000000', lookup_status='completed', nombre_completo='Persona de prueba',
            procesos_actor_total=12, procesos_demandado_total=1,
            funcion_judicial_data={
                'procesos_actor': [{'idJuicio': 'ACTOR-TEST', 'fechaIngreso': '2026-01-01', 'nombreDelito': 'Asunto de prueba'}],
                'procesos_demandado': [{'idJuicio': 'DEMANDADO-TEST', 'nombreMateria': 'Materia de prueba'}],
            },
            normalized_data={'supa': {'registros_total': 1, 'tiene_registros': True, 'tablas': [[['Código', 'Estado'], ['SUPA-TEST', 'Dato de prueba']]]}},
        )

    def page(self):
        return self.client.get(reverse('global_person_lookup'), {'cedula': self.record.cedula})

    def test_displays_actor_defendant_and_supa_details(self):
        response = self.page()
        for text in ('Procesos como actor', 'Procesos como demandado', 'ACTOR-TEST', 'DEMANDADO-TEST', 'SUPA-TEST', 'El detalle guardado es parcial.'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'json-pane')
        self.assertNotContains(response, 'personLookupDetailModal')

    def test_source_failure_is_not_presented_as_no_results(self):
        self.record.source_errors = {'supa': 'PRIVATE endpoint /internal/', 'funcion_judicial': 'PRIVATE traceback'}
        self.record.funcion_judicial_data = {}
        self.record.normalized_data = {'supa': {'registros_total': 0, 'tablas': [], 'tiene_registros': False}}
        self.record.save()
        response = self.page()
        self.assertContains(response, 'No confirmado')
        self.assertContains(response, 'SUPA sin confirmar')
        self.assertNotContains(response, 'SUPA sin registros')
        self.assertNotContains(response, 'PRIVATE')

    def test_external_strings_are_escaped(self):
        self.record.funcion_judicial_data = {'procesos_actor': [{'idJuicio': '<script>alert(1)</script>'}], 'procesos_demandado': []}
        self.record.normalized_data = {'supa': {'registros_total': 1, 'tablas': [[['Dato'], ['<img src=x onerror=alert(1)>']]]}}
        self.record.save()
        response = self.page()
        self.assertContains(response, '&lt;script&gt;')
        self.assertContains(response, '&lt;img')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, '<img src=x')

    def test_old_or_malformed_stored_data_does_not_crash(self):
        for data in ({}, {'procesos_actor': 'invalid'}, {'procesos_actor': [None, 'invalid', {'idJuicio': {'nested': 'value'}}]}):
            self.record.funcion_judicial_data = data
            self.record.normalized_data = {'supa': {'tablas': [None, [], 'invalid', [['A'], ['B', 'C']]]}}
            self.record.save()
            self.assertEqual(self.page().status_code, 200)
