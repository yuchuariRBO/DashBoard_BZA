"""Regression checks for connector discovery and isolated logging routes."""
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from gestion_personal.person_lookup import CONSULTA_PEOPLE_DIR
from gestion_personal.plate_lookup import CONSULTA_PLATES_DIR
from gestion_personal.services.lookup_sources import load_source_module


class ProjectLayoutTests(SimpleTestCase):
    def test_external_sources_remain_loadable_without_running_queries(self):
        for directory, method in ((CONSULTA_PEOPLE_DIR, 'consultar_cedula'), (CONSULTA_PLATES_DIR, 'consultar_placa')):
            sources = list(directory.glob('consulta_*.py'))
            self.assertTrue(sources)
            self.assertEqual(directory.parent.name, 'integrations')
            for source in sources:
                with self.subTest(source=source.name):
                    module = load_source_module(directory, source.stem)
                    self.assertTrue(callable(getattr(module, method, None)) or callable(getattr(module, 'consultar_nombre', None)))

    def test_logging_writes_by_category_and_duplicates_errors(self):
        # Configure logging in a separate interpreter to preserve Django's handlers.
        script = """
import logging, logging.config, sys
from inventario_bonanza.logging_config import build_logging_config
logging.config.dictConfig(build_logging_config(sys.argv[1]))
logging.getLogger('gestion_personal').info('APP_MARKER')
logging.getLogger('django.security.csrf').warning('SECURITY_MARKER')
logging.getLogger('gestion_personal.management.commands.lookup_person').info('PEOPLE_MARKER')
logging.getLogger('gestion_personal.management.commands.lookup_plate').error('PLATES_ERROR_MARKER')
logging.getLogger('gestion_personal.services.notifications').info('NOTIFICATION_MARKER')
logging.shutdown()
"""
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([sys.executable, '-B', '-c', script, temporary], check=True, capture_output=True, cwd=Path(__file__).resolve().parents[2])
            root = Path(temporary)
            for relative, marker in (
                ('application/django.log', 'APP_MARKER'),
                ('security/security.log', 'SECURITY_MARKER'),
                ('lookups/people/people.log', 'PEOPLE_MARKER'),
                ('lookups/plates/plates.log', 'PLATES_ERROR_MARKER'),
                ('errors/errors.log', 'PLATES_ERROR_MARKER'),
                ('notifications/notifications.log', 'NOTIFICATION_MARKER'),
            ):
                self.assertIn(marker, (root / relative).read_text())
            self.assertNotIn('PEOPLE_MARKER', (root / 'application/django.log').read_text())
