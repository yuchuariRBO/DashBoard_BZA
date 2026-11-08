# Alertas de Fail2ban por Telegram

1. Aplica la migración `0019_telegramalertsettings` con `manage.py migrate`.
2. En la pestaña **Alertas**, guarda el token del bot y al menos un ID de alertas del servidor.
3. Copia `telegram-robio.conf` a `/etc/fail2ban/action.d/telegram-robio.conf`.
4. Añade `telegram-robio` a las acciones del jail `sshd`, por ejemplo:

```ini
[sshd]
action = %(action_)s
         telegram-robio
```

Conserva cualquier otra acción existente del jail. Comprueba la configuración con
`fail2ban-client -t` antes de reiniciar Fail2ban. El comando puede probarse con
`manage.py send_fail2ban_alert 192.0.2.1 --service SSH`.
