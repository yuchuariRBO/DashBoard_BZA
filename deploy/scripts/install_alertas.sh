#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo 'Ejecuta este script como root.' >&2
  exit 1
fi

APP=/root/bonanza/inventario_bonanza
PYTHON=/root/bonanza/venv/bin/python
ACTION=/etc/fail2ban/action.d/telegram-robio.conf
JAIL=/etc/fail2ban/jail.d/zz-bonanza-telegram.local

"$PYTHON" "$APP/manage.py" migrate --noinput
install -m 0644 "$APP/../deploy/security/fail2ban/action.d/telegram-robio.conf" "$ACTION"
if [[ -e $JAIL ]]; then
  echo "Ya existe $JAIL; revísalo antes de continuar." >&2
  exit 1
fi
cat > "$JAIL" <<'EOF'
[sshd]
action = %(action_)s
         telegram-robio
EOF

if ! fail2ban-client -t; then
  rm -f "$JAIL"
  echo 'Configuración de Fail2ban inválida; se retiró la nueva regla.' >&2
  exit 1
fi
systemctl restart bonanza-gunicorn
systemctl restart fail2ban
for attempt in 1 2 3 4 5; do
  if fail2ban-client get sshd actions 2>/dev/null | grep -q 'telegram-robio'; then
    echo 'Alertas instaladas. Configura el bot y los IDs en la pestaña Alertas.'
    exit 0
  fi
  sleep 1
done
echo 'Fail2ban inició, pero la acción telegram-robio no aparece en sshd.' >&2
exit 1
