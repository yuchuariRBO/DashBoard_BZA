# Limpieza semanal de la VM

## Programación y alcance

`bonanza-weekly-cleanup.timer` inicia `bonanza-weekly-cleanup.service` cada domingo
a las **03:30 UTC**, con hasta 15 minutos de retraso aleatorio. `Persistent=true`
permite recuperar una ejecución perdida cuando la VM o el timer vuelven a activarse.
No se reinicia el dashboard para limpiar y no se requiere acceso a internet.

La limpieza ejecuta exclusivamente estas operaciones:

| Operación | Regla |
|---|---|
| Paquetes APT descargados | `apt-get clean`; no desinstala paquetes ni ejecuta autoremove |
| Journal del sistema archivado | Elimina archivos archivados por antigüedad de 14 días o tamaño de 300M; no trunca el journal activo |
| Logs del proyecto | Ejecuta la regla instalada de logrotate sin forzar; conserva la retención de 14 copias |
| Caché de pip | Borra solo archivos regulares con modificación anterior a 30 días de las dos rutas permitidas |
| Descargas de extensiones VS Code | Misma regla de 30 días, solo en `data/CachedExtensionVSIXs`; conserva extensiones y servidores instalados |

Las únicas raíces de caché recorridas son `/root/.cache/pip`,
`/home/robiotec/.cache/pip`, `/root/.vscode-server/data/CachedExtensionVSIXs`
y `/home/robiotec/.vscode-server/data/CachedExtensionVSIXs`. Las rutas ausentes se
omiten y no se siguen enlaces simbólicos. La antigüedad se mide por modificación,
no por fecha del último acceso. Las carpetas vacías se conservan.

No se recorren SQLite, `MinIO/`, `media/`, fotografías, documentos, consultas guardadas,
respaldos, `.env`, `.git`, `venv/`, `staticfiles/`, `run/`, el código del proyecto,
los navegadores de Playwright ni los temporales generales de usuarios.
La unidad monta el sistema en solo lectura y habilita escritura únicamente en
las ubicaciones operativas necesarias. Usa un bloqueo propio en
`/run/bonanza-maintenance/cleanup.lock`, baja prioridad de CPU/disco y un límite
de memoria de 256M. No usa los bloqueos de consultas del dashboard.

## Instalación

Revisar las rutas si se instala fuera de esta VM. Instalar primero la regla de
rotación del proyecto si todavía no existe. Los siguientes comandos son de
administración y se ejecutan desde la raíz del repositorio:

```bash
sudo install -m 0644 deploy/systemd/bonanza-weekly-cleanup.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/bonanza-weekly-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bonanza-weekly-cleanup.timer
```

El script se ejecuta con Python del sistema; no necesita cargar `.env`, importar
Django ni conectarse a la base de datos. Los cambios del script se usan en la
siguiente ejecución. Tras cambiar una unidad o el horario, volver a instalar
el archivo, ejecutar `daemon-reload` y reiniciar el timer.

## Verificación y ejecución manual

```bash
# Simulación: no borra archivos, no escribe logs ni crea un bloqueo.
sudo python3 -B deploy/scripts/weekly_cleanup.py --dry-run

# Pruebas con archivos ficticios y enlaces simbólicos en un directorio temporal.
python3 -B -m unittest discover -s deploy/tests -v

# Ver programación y ejecutar de inmediato usando las restricciones del servicio.
systemctl list-timers bonanza-weekly-cleanup.timer --all
sudo systemctl start bonanza-weekly-cleanup.service
sudo systemctl status bonanza-weekly-cleanup.service --no-pager
sudo journalctl -u bonanza-weekly-cleanup.service -n 100 --no-pager
sudo tail -n 50 logs/maintenance/weekly-cleanup.log
```

Un servicio `Type=oneshot` queda normalmente `inactive (dead)` después de terminar
correctamente. Verificar `Result=success` y `ExecMainStatus=0`; lo que debe permanecer
activo y habilitado es el **timer**. El log contiene los pasos y el espacio libre
antes y después. La diferencia puede variar por las escrituras simultáneas de la VM.
El archivo de mantenimiento también queda sujeto a la rotación de Bonanza.

Si APT está ocupado o falla un paso, el script continúa con los demás y termina
con código 1 para que systemd registre el fallo. Si logrotate ya tiene su bloqueo,
ese paso se omite sin duplicar la rotación. Revisar el journal y volver a iniciar
el servicio después de resolver el problema. No se envían notificaciones automáticas.

Para suspender la programación:

```bash
sudo systemctl disable --now bonanza-weekly-cleanup.timer
```

Esto no detiene una limpieza que ya haya comenzado. Si fuera necesario, detener
también `bonanza-weekly-cleanup.service`. La limpieza no sustituye a los respaldos,
a la supervisión del espacio libre ni al mantenimiento de actualizaciones.
