"""Envía una alerta de bloqueo desde una acción de Fail2ban."""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gestion_personal.services.notifications import send_server_security_alert


class Command(BaseCommand):
    help = 'Envía a Telegram una alerta de IP bloqueada por Fail2ban.'

    def add_arguments(self, parser):
        parser.add_argument('ip', help='IP bloqueada')
        parser.add_argument('--service', default='SSH', help='Servicio o jail')
        parser.add_argument('--server', default='BZA', help='Nombre del servidor')
        parser.add_argument('--reason', default='Bloqueo de Fail2ban', help='Motivo')

    def handle(self, *args, **options):
        from gestion_personal.services.notifications import telegram_configuration
        token, ids = telegram_configuration('server')
        if not token or not ids:
            raise CommandError('Configura el bot y los IDs de alertas del servidor antes de enviar.')
        send_server_security_alert(
            options['ip'], timezone.localtime().strftime('%d/%m/%Y %H:%M %Z'),
            options['reason'], options['service'], options['server'],
        )
        self.stdout.write(self.style.SUCCESS('Alerta de seguridad procesada.'))
