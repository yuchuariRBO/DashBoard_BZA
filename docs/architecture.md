# Estructura y operación de Bonanza

```text
bonanza/
├── inventario_bonanza/         # Aplicación Django y activos web
│   ├── manage.py
│   ├── inventario_bonanza/     # Settings, URLs, WSGI y configuración de logging
│   ├── gestion_personal/      # Dominio de personal y capa HTTP
│   │   ├── services/          # Reglas de negocio reutilizables
│   │   ├── management/commands/
│   │   ├── migrations/        # Historial de esquema: conservar completo
│   │   ├── templates/
│   │   └── tests/             # Pruebas organizadas por responsabilidad
│   ├── static/               # Fuentes versionadas
│   ├── staticfiles/           # Salida de collectstatic; Nginx la usa
│   ├── media/                 # Compatibilidad con almacenamiento local
│   ├── db.sqlite3             # Datos persistentes; excluidos de Git
│   └── service_unavailable.html
├── integrations/
│   ├── people/               # Conectores externos de personas
│   └── plates/               # Conectores externos de placas
├── deploy/
│   ├── systemd/              # Servicios y temporizador; sin secretos
│   ├── nginx/                # Sitios y páginas de error
│   ├── logrotate/            # Rotación y retención de logs
│   ├── security/             # SSH y Fail2ban
│   └── scripts/              # Herramientas de instalación manual
├── docs/                     # Arquitectura, auditorías y operación
├── logs/                     # Archivos operativos, excluidos de Git
│   ├── application/django.log
│   ├── errors/errors.log
│   ├── security/security.log
│   ├── notifications/notifications.log
│   ├── lookups/people/        # people.log y worker.log
│   ├── lookups/plates/        # plates.log y worker.log
│   └── gunicorn/             # access.log y error.log
├── run/                      # Bloqueos de concurrencia; no borrar en ejecución
├── MinIO/                    # Fotografías y documentos; no manipular a mano
├── venv/                     # Dependencias activas de Python
├── .env                      # Credenciales locales; nunca versionar
└── requirements.txt
```

## Límites entre componentes

Las vistas y URLs implementan HTTP y permisos. `services/` reúne reglas de negocio,
consultas y notificaciones. Los conectores de `integrations/` se cargan por ruta;
no se deben ejecutar directamente sobre datos reales para comprobar un despliegue.
Los comandos de Django coordinan las consultas en segundo plano.

La base SQLite y el volumen MinIO conservan sus rutas desplegadas: existen servicios
y sincronizadores que las conocen. Moverlos exige un plan independiente de migración,
parada y restauración. Los archivos estáticos recopilados también conservan la ruta
que sirve Nginx. El respaldo previo a esta reorganización se guarda fuera del proyecto,
en `/root/bonanza-backups/`, con permisos restringidos.

## Servicios

`deploy/systemd/` contiene copias revisables de las unidades de esta VM. Las unidades
activas están en `/etc/systemd/system/`. Gunicorn sirve Django en 127.0.0.1:8000;
Nginx publica HTTPS; MinIO guarda los objetos. La unidad de placas y su temporizador
vigilan la cola. Los workers iniciados desde Django usan `run/` para sus bloqueos.
No instalar las plantillas automáticamente sobre una configuración personalizada.
El cambio de logs de Gunicorn se aplica mediante el drop-in `logging.conf` incluido.

Los logs de sistema de MinIO, el worker de systemd y Nginx siguen en sus ubicaciones
administradas: `journalctl -u minio`, `journalctl -u bonanza-plate-lookup-drain`
y `/var/log/nginx/`. No se duplican dentro del repositorio. Los logs de Gunicorn y
de Django sí se agrupan en `logs/` como muestra el árbol.

## Logs y rotación

`LOG_DIR` permite cambiar la raíz de logs; `RUN_DIR` permite cambiar la de bloqueos.
Las rutas por defecto son `/root/bonanza/logs` y `/root/bonanza/run` en esta VM.
Los errores de nivel ERROR o superior también se guardan en `errors/errors.log`.
Django usa `WatchedFileHandler`, que reabre el archivo tras la rotación externa y
evita que varios workers roten el mismo archivo. La regla `deploy/logrotate/bonanza`
se instala en `/etc/logrotate.d/bonanza`: rotación diaria, 14 copias y compresión.
`maxsize 25M` se evalúa cuando corre logrotate; no es un límite instantáneo.
Gunicorn y el log de salida del worker usan copytruncate para conservar sus descriptores;
existe una pequeña ventana de posible pérdida de líneas durante esa rotación.
Los logs pueden contener identificadores; se deben proteger y no subir a Git.

## Validación

```bash
venv/bin/python inventario_bonanza/manage.py check
venv/bin/python inventario_bonanza/manage.py test gestion_personal --noinput
git diff --check
systemctl is-active bonanza-gunicorn nginx minio
```

Las pruebas usan una base temporal. Nunca usar la base de producción como base de pruebas.
No eliminar migraciones, archivos de datos, dependencias ni activos estáticos como limpieza.

## Reorganización aplicada el 8 de noviembre de 2026

- 88 pruebas aprobadas, con SQLite temporal y logs de pruebas separados.
- Django check, revisión de migraciones y git diff --check sin incidencias.
- Página de login HTTPS mediante Nginx: 200; salud de MinIO: 200.
- Gunicorn, Nginx, MinIO y el temporizador de placas activos.
- SQLite quick_check: ok; 368 personas, 19.976 placas y 29 consultas de personas.
- Los archivos del bucket de personal conservan tamaño y fecha de modificación.
  Los metadatos temporales internos de MinIO cambian durante su operación normal.
- Regla de logrotate instalada y validada en modo de simulación.
- Respaldo de datos: `/root/bonanza-backups/db.sqlite3.before-reorganization-20261108`.
- Copia previa del código: `/tmp/bonanza-before-reorganization/source.tar.gz`.
  Es una copia temporal para esta intervención, no un respaldo externo automático.
