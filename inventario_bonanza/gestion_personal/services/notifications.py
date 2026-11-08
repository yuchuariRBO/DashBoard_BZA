"""Canales de notificación externos.

Mantener las llamadas HTTP aquí evita que los modelos y las vistas conozcan los
detalles del API de Telegram.
"""

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)
TELEGRAM_CAPTION_LIMIT = 1024


def _chat_ids(value):
    return list(dict.fromkeys(part.strip() for part in value.replace('\n', ',').split(',') if part.strip()))


def telegram_configuration(category='common'):
    """Lee la configuración editable; conserva las variables de entorno como respaldo."""
    from django.db.utils import OperationalError, ProgrammingError
    from gestion_personal.models import TelegramAlertSettings

    config = None
    try:
        config = TelegramAlertSettings.objects.order_by('pk').first()
    except (OperationalError, ProgrammingError):
        pass  # La migración aún puede no haberse aplicado.
    token = (config.bot_token if config and config.bot_token else getattr(settings, 'TELEGRAM_BOT_TOKEN', ''))
    if category == 'server':
        ids = _chat_ids(config.server_chat_ids) if config else []
    else:
        ids = _chat_ids(config.common_chat_ids) if config else []
        if not config:
            ids = getattr(settings, 'TELEGRAM_CHAT_IDS', [])
    return token, ids


def format_server_security_alert(ip, date, reason, service='SSH', server='BZA'):
    """Formato de los eventos de seguridad de Fail2ban."""
    return (f'ALERTAS DE SEGURIDAD ROBIOTEC\n'
            f'Servidor: {server}\n'
            f'Servicio: {service}\n'
            f'IP Bloqueada: {ip}\n'
            f'Fecha: {date}\n'
            f'Motivo: {reason}')


def send_server_security_alert(ip, date, reason, service='SSH', server='BZA'):
    send_telegram_message(
        format_server_security_alert(ip, date, reason, service, server),
        category='server',
    )


def send_telegram_message(message, photo=None, category='common'):
    """Envía un mensaje a los chats configurados, sin bloquear el flujo ante fallos."""
    token, chat_ids = telegram_configuration(category)
    if not token or not chat_ids:
        return {'sent': 0, 'failed': 0}

    caption = message.strip()
    if len(caption) > TELEGRAM_CAPTION_LIMIT:
        caption = f'{caption[:TELEGRAM_CAPTION_LIMIT - 24]}\n...'

    sent = 0
    failed = 0
    for chat_id in chat_ids:
        try:
            if photo:
                photo.open('rb')
                try:
                    response = requests.post(
                        f'https://api.telegram.org/bot{token}/sendPhoto',
                        data={'chat_id': chat_id, 'caption': caption},
                        files={'photo': photo.file},
                        timeout=15,
                    )
                finally:
                    photo.close()
            else:
                response = requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    data={'chat_id': chat_id, 'text': caption},
                    timeout=15,
                )
            response.raise_for_status()
            sent += 1
        except requests.RequestException:
            failed += 1
            logger.warning('No se pudo enviar una notificación de Telegram.')
    return {'sent': sent, 'failed': failed}


def send_email_notification(subject, message, recipients):
    """Envía un correo a una colección de direcciones válidas y sin duplicados."""
    recipient_list = list(dict.fromkeys(email for email in recipients if email))
    if not recipient_list:
        return
    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'registrodatos@grupominerobonanza.com',
            recipient_list,
            fail_silently=True,
        )
    except Exception:
        logger.exception('No se pudo enviar la notificación por correo.')
