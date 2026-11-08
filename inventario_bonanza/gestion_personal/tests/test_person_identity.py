from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from ..models import CustomUser, PersonLookupRecord
from ..services.person_identity import judicial_name, stored_identity
from ..person_lookup import save_person_lookup_result


class JudicialNameTests(SimpleTestCase):
    def test_matches_only_the_requested_participant(self):
        payload = {'procesos_demandado': [{'litigantes': [
            {'identificacion': '1111111111', 'nombre': 'OTRA PERSONA'},
            {'identificacion': '0000000000', 'nombre': 'PERSONA DE PRUEBA'},
        ]}]}
        self.assertEqual(judicial_name(payload, '0000000000'), 'PERSONA DE PRUEBA')

    def test_role_specific_name_and_id_pairs(self):
        payload = {'procesos_actor': [{'cedulaActor': '1111111111', 'nombreActor': 'OTRO ACTOR', 'cedulaProcesado': '0000000000', 'nombreProcesado': 'PERSONA DE PRUEBA'}]}
        self.assertEqual(judicial_name(payload, '0000000000'), 'PERSONA DE PRUEBA')

    def test_name_without_matching_identifier_is_not_used(self):
        self.assertEqual(judicial_name({'cedula': '0000000000', 'items': [{'nombreDemandado': 'OTRA PERSONA'}]}, '0000000000'), '')
        self.assertEqual(judicial_name({'nombreDemandado': 'OTRA PERSONA', 'cedulaDemandado': '1111111111'}, '0000000000'), '')

    def test_conflicting_names_are_not_guessed(self):
        self.assertEqual(judicial_name([{'cedula': '0000000000', 'nombre': 'ANA PEREZ'}, {'cedula': '0000000000', 'nombre': 'JUAN LOPEZ'}], '0000000000'), '')

    def test_malformed_data_is_ignored(self):
        for value in (None, '', 42, [None, {'cedula': {}, 'nombre': ['invalid']} ]):
            self.assertEqual(judicial_name(value, '0000000000'), '')


@override_settings(SECURE_SSL_REDIRECT=False)
class StoredIdentityTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='identity-test', user_type='global_admin')
        self.client.force_login(self.user)
        self.payload = {'procesos_demandado': [{'demandados': [{'cedula': '0000000000', 'nombreCompleto': 'PERSONA DE PRUEBA'}]}]}
        self.record = PersonLookupRecord.objects.create(cedula='0000000000', nombre_completo='', lookup_status='completed', funcion_judicial_data=self.payload)

    def test_old_record_displays_name_without_requery(self):
        response = self.client.get(reverse('global_person_lookup'), {'cedula': self.record.cedula})
        self.assertContains(response, 'PERSONA DE PRUEBA')
        self.assertContains(response, 'Función Judicial · cédula coincidente')
        self.record.refresh_from_db()
        self.assertEqual(self.record.nombre_completo, '')

    def test_worker_persists_recovered_name(self):
        result = {'cedula': self.record.cedula, 'normalized': {'nombre_completo': '', 'procesos_actor_total': 0, 'procesos_demandado_total': 1, 'citaciones_total': 0}, 'sources': {'funcion_judicial': self.payload}}
        save_person_lookup_result(result, record=self.record)
        self.record.refresh_from_db()
        self.assertEqual(self.record.nombre_completo, 'PERSONA DE PRUEBA')
        self.assertEqual(self.record.normalized_data['nombre_completo'], 'PERSONA DE PRUEBA')

    def test_existing_name_is_preferred(self):
        self.record.nombre_completo = 'NOMBRE EXISTENTE'
        self.assertEqual(stored_identity(self.record)['name'], 'NOMBRE EXISTENTE')

    def test_other_stored_source_can_fill_name(self):
        self.record.sri_data = {'nombre_completo': 'NOMBRE SRI', 'identificacion': self.record.cedula}
        self.assertEqual(stored_identity(self.record)['name'], 'NOMBRE SRI')
        self.record.sri_data['identificacion'] = '1111111111'
        self.assertEqual(stored_identity(self.record)['name'], 'PERSONA DE PRUEBA')
