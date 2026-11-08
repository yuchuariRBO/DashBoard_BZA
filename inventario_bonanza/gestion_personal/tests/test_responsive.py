"""Template and navigation contracts shared by the responsive interface."""
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase


class ResponsiveTemplateTests(SimpleTestCase):
    def test_all_templates_compile(self):
        root = Path(settings.BASE_DIR) / 'gestion_personal' / 'templates'
        for path in root.rglob('*.html'):
            with self.subTest(template=path.name):
                get_template(str(path.relative_to(root)))

    def test_mobile_navigation_controls_existing_role_links(self):
        user = SimpleNamespace(is_authenticated=True, user_type='rh', username='test')
        html = render_to_string('gestion_personal/base.html', {
            'user': user, 'request': SimpleNamespace(path='/rh/dashboard/'),
        })
        soup = BeautifulSoup(html, 'html.parser')
        toggle = soup.select_one('[data-bs-target="#sidebarMenu"]')
        self.assertEqual(toggle['aria-controls'], 'sidebarMenu')
        self.assertEqual(toggle['aria-expanded'], 'false')
        menu = soup.select_one('#sidebarMenu.collapse')
        self.assertTrue(menu.select('a[href]'))
        self.assertTrue(menu.select_one('a.active'))
        self.assertTrue(soup.select_one('script[src$="js/responsive.js"]'))

    def test_responsive_static_assets_are_discoverable(self):
        for asset in ('css/platform.css', 'js/responsive.js', 'js/qr-scanner.js', 'img/logo.png'):
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))
