#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo 'Ejecuta este script como root.' >&2
  exit 1
fi
if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo 'Root necesita una clave pública en /root/.ssh/authorized_keys antes de habilitar SSH.' >&2
  exit 1
fi

CONFIG=/etc/ssh/sshd_config.d/10-bonanza-hardening.conf
BACKUP="${CONFIG}.backup.$(date +%Y%m%d%H%M%S)"
cp -p "$CONFIG" "$BACKUP"
python3 - "$CONFIG" <<'PYINNER'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
if 'AllowUsers robiotec' not in s or not any(
    rule in s for rule in ('PermitRootLogin no', 'PermitRootLogin prohibit-password')
):
    raise SystemExit('Las reglas SSH esperadas cambiaron; revisa el archivo manualmente.')
s = s.replace('PermitRootLogin no', 'PermitRootLogin prohibit-password', 1)
s = s.replace('AllowUsers robiotec', 'AllowUsers robiotec root', 1)
p.write_text(s)
PYINNER
if ! sshd -t; then
  cp -p "$BACKUP" "$CONFIG"
  echo 'Configuración SSH inválida; se restauró el respaldo.' >&2
  exit 1
fi
systemctl reload ssh
echo "Acceso root por clave habilitado. Respaldo: $BACKUP"
