from unittest.mock import patch
from django.test import SimpleTestCase, Client, override_settings
from django.urls import path
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from . import error_views


def broken(request):
    raise RuntimeError('PRIVATE-TOKEN /internal/service/api/')


def forbidden(request):
    raise PermissionDenied('PRIVATE-TOKEN')


def invalid(request):
    raise SuspiciousOperation('PRIVATE-TOKEN')


urlpatterns = [path('broken/', broken), path('forbidden/', forbidden), path('invalid/', invalid)]
handler400 = error_views.bad_request
handler403 = error_views.forbidden
handler404 = error_views.not_found
handler500 = error_views.server_error


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class PublicErrorTests(SimpleTestCase):
    def test_missing_page_hides_routes_and_input(self):
        response = self.client.get('/PRIVATE-TOKEN/nonexistent/')
        self.assertContains(response, 'Página no disponible', status_code=404)
        self.assertNotContains(response, 'PRIVATE-TOKEN', status_code=404)
        self.assertNotContains(response, 'urlpatterns', status_code=404)
        self.assertEqual(response['Cache-Control'], 'no-store')

    @override_settings(ROOT_URLCONF=__name__)
    def test_exception_details_never_reach_browser(self):
        client = Client(raise_request_exception=False)
        for url, status in [('/broken/', 500), ('/forbidden/', 403), ('/invalid/', 400)]:
            response = client.get(url)
            self.assertEqual(response.status_code, status)
            self.assertNotContains(response, 'PRIVATE-TOKEN', status_code=status)
            self.assertNotContains(response, 'Traceback', status_code=status)
            self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_api_missing_route_returns_generic_json(self):
        response = self.client.get('/api/PRIVATE-TOKEN/')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['ok'])
        self.assertNotIn('PRIVATE-TOKEN', response.content.decode())

    def test_csrf_failure_hides_reason(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/login/', {'username': 'test', 'password': 'PRIVATE-TOKEN'})
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'CSRF', status_code=403)
        self.assertNotContains(response, 'PRIVATE-TOKEN', status_code=403)

    @override_settings(PLATE_LOOKUP_API_TOKEN='secret', PERSON_LOOKUP_API_TOKEN='secret', FACE_GALLERY_API_TOKEN='secret')
    def test_external_apis_require_token_before_accessing_data(self):
        for url in ('/api/plate-lookup/ABC1234/', '/api/person-lookup/0102030405/', '/api/face-gallery/people/'):
            self.assertEqual(self.client.get(url).status_code, 401)
            self.assertEqual(self.client.get(url, HTTP_X_PERSON_LOOKUP_TOKEN='wrong', HTTP_X_PLATE_LOOKUP_TOKEN='wrong', HTTP_X_FACE_GALLERY_TOKEN='wrong').status_code, 401)
