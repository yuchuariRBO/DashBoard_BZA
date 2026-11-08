# DashboardBZA

Plataforma Django para gestionar personal, organizaciones, accesos, visitantes, vehículos, consultas externas y procesos de Recursos Humanos de Bonanza.

Este documento describe el código y la operación de la VM verificados el **8 de noviembre de 2026**. Las rutas absolutas corresponden a esa instalación; deben adaptarse al desplegar en otro servidor.

| Recurso | Ubicación |
|---|---|
| Aplicación | https://bonanza.robio-ai.com |
| Repositorio principal, `origin` | [yuchuariRBO/DashBoard_BZA](https://github.com/yuchuariRBO/DashBoard_BZA) |
| Repositorio anterior, `upstream` | [Robiotec/DashBoard_BZA](https://github.com/Robiotec/DashBoard_BZA) |
| Rama de despliegue | `main` |
| Proyecto en la VM | `/root/bonanza` |
| Arquitectura y reorganización | [docs/architecture.md](docs/architecture.md) |

## Índice

- [Funciones y perfiles](#funciones-y-perfiles)
- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Datos y archivos persistentes](#datos-y-archivos-persistentes)
- [Requisitos e instalación local](#requisitos-e-instalación-local)
- [Variables de entorno](#variables-de-entorno)
- [Servicios de producción](#servicios-de-producción)
- [Actualizar un despliegue existente](#actualizar-un-despliegue-existente)
- [Logs y rotación](#logs-y-rotación)
- [Consultas externas y procesamiento](#consultas-externas-y-procesamiento)
- [Rutas web y APIs](#rutas-web-y-apis)
- [Respaldos y recuperación](#respaldos-y-recuperación)
- [Pruebas y validación](#pruebas-y-validación)
- [Diagnóstico de problemas](#diagnóstico-de-problemas)
- [Mantenimiento y seguridad](#mantenimiento-y-seguridad)
- [Documentación complementaria](#documentación-complementaria)

## Funciones y perfiles

La plataforma incluye fichas de personal con fotografías, gestión de organizaciones y usuarios, ingresos y salidas, visitantes y visitas programadas, vehículos, permisos, vacaciones, jornadas, sanciones, atención médica, asignación de EPP, alojamiento, comedores, importaciones y exportaciones. Los módulos de RRHH también contemplan actividades, novedades y documentos de respaldo.

| Perfil del modelo | Área principal |
|---|---|
| `global_admin` | Administración global o administración limitada a su organización, según la asignación del usuario |
| `rh` | Personal, jornadas, vacaciones y procesos de Recursos Humanos |
| `operador` | Registro operativo de ingresos, salidas, vehículos y visitantes |
| `medico` | Atención y revisión médica |
| `admin_mina`, `admin_molino` | Administración de su ámbito y visitas programadas |
| `seguridad_fisica` | Control de accesos y registros de seguridad |
| `tecnico_seguridad` | Gestión de seguridad y asignación de EPP |

Los permisos concretos se aplican en las vistas, formularios y servicios de alcance. Un administrador global sin organización representa al administrador del sistema. La información operativa de las organizaciones tiene filtros de acceso; las **consultas guardadas de personas y placas forman una base compartida entre usuarios autorizados**, conforme a la política actual. No debe asumirse que esas consultas están aisladas por empresa.

## Arquitectura

```text
Navegador / integración autorizada
              │ HTTPS
              ▼
            Nginx ───────────────► staticfiles/ (CSS, JS e imágenes del sitio)
              │ HTTP interno
              ▼
      Gunicorn 127.0.0.1:8000
              │
          Django / permisos
         ┌────┼───────────────┐
         ▼    ▼               ▼
      SQLite MinIO       Comandos de consulta
               │               │
     Fotografías/documentos    ▼
                        integrations/ → fuentes externas
```

Las vistas implementan la capa HTTP y la autorización. `gestion_personal/services/` contiene reglas reutilizables de dominio, métricas, notificaciones y filtros. Los comandos de Django ejecutan trabajos de consulta con control de concurrencia. Los conectores externos se cargan desde `integrations/` y sus resultados se guardan en SQLite.

Los archivos privados se entregan a través de Django con comprobaciones de acceso. Nginx sirve los archivos estáticos recopilados y termina HTTPS. MinIO escucha en interfaces locales; su volumen en disco contiene los objetos y metadatos internos.

## Estructura del proyecto

```text
bonanza/
├── inventario_bonanza/
│   ├── manage.py                         # Comandos de Django
│   ├── inventario_bonanza/
│   │   ├── settings.py                   # Configuración y lectura de .env
│   │   ├── logging_config.py             # Separación de logs por categoría
│   │   ├── urls.py                       # Rutas principales
│   │   ├── wsgi.py                       # Entrada para Gunicorn
│   │   └── asgi.py
│   ├── gestion_personal/
│   │   ├── models.py                     # Datos del dominio
│   │   ├── forms.py                      # Validación de formularios
│   │   ├── views.py / urls.py             # HTTP y navegación
│   │   ├── hr_management.py              # Módulos de RRHH
│   │   ├── person_lookup.py              # Coordinación de consultas de personas
│   │   ├── plate_lookup.py               # Coordinación de consultas de placas
│   │   ├── storage_backends.py           # Acceso de Django a MinIO
│   │   ├── services/                     # Lógica reutilizable
│   │   ├── management/commands/          # Jobs y herramientas de operación
│   │   ├── migrations/                   # Historial del esquema
│   │   ├── templates/                    # HTML organizado por módulo y perfil
│   │   └── tests/                        # Pruebas de regresión
│   ├── static/                           # Activos fuente versionados
│   ├── staticfiles/                      # Resultado de collectstatic; local
│   ├── media/                            # Compatibilidad con archivos locales
│   ├── db.sqlite3                        # Base de datos activa; local
│   └── service_unavailable.html          # Página estática de indisponibilidad
├── integrations/
│   ├── people/                           # Conectores de personas
│   └── plates/                           # Conectores de placas
├── deploy/
│   ├── systemd/                          # Unidades, timer y drop-ins
│   ├── nginx/                            # Sitios y configuración de errores
│   ├── logrotate/bonanza                 # Retención de logs
│   ├── security/                         # SSH y Fail2ban
│   └── scripts/                          # Herramientas de instalación manual
├── docs/
│   ├── architecture.md
│   ├── audits/
│   └── operations/
├── logs/                                 # Logs operativos; no versionados
├── run/                                  # Bloqueos de procesos; no versionados
├── MinIO/                                # Volumen persistente; no versionado
├── venv/                                 # Entorno Python activo; no versionado
├── .env                                  # Secretos de la instalación; no versionado
├── .env.example                          # Ejemplo de configuración
├── .gitignore
└── requirements.txt
```

Los directorios `consulta_people/` y `consulta_plates/` se consolidaron en `integrations/`. La documentación y los scripts que estaban dentro de `inventario_bonanza/deploy/` pasaron a `docs/` y `deploy/`. Los antiguos archivos `test_*.py` y `tests.py` se agruparon en `gestion_personal/tests/`.

### Servicios de dominio

| Archivo en `gestion_personal/services/` | Responsabilidad |
|---|---|
| `scoping.py`, `roles.py` | Alcance por organización y navegación por perfil |
| `hr_dashboard.py`, `hr_analytics.py` | Indicadores y contexto de tableros |
| `people_import.py`, `person_search.py`, `detailed_people.py` | Importación y búsqueda de personal |
| `person_identity.py`, `person_lookup_presentation.py` | Identidad y presentación de resultados guardados |
| `lookup_sources.py` | Carga y ejecución controlada de conectores |
| `notifications.py` | Notificaciones por correo y Telegram |
| `dates.py`, `workdays.py`, `record_metrics.py` | Fechas, jornadas y métricas de registros |

## Datos y archivos persistentes

| Contenido | Ubicación actual | Observación |
|---|---|---|
| Datos del personal y consultas | `inventario_bonanza/db.sqlite3` | Una sola base SQLite contiene las tablas de los distintos módulos |
| Fotografías y documentos | `MinIO/dashboard-personal/` | Bucket configurado actualmente; MinIO administra su estructura interna |
| Fotografías de personal | Objetos `personas/activos/` y `personas/pasivos/` | El nombre generado por el modelo usa la cédula y extensión `.png` |
| Documentos de renuncia | Objetos `renuncias/` | El modelo genera rutas de documentos PDF |
| Credenciales | `.env` | Necesarias para conectar servicios y APIs |
| Respaldos locales | `/root/bonanza-backups/` | Fuera del repositorio de trabajo |

La base guarda las referencias a las fotografías; los bytes de las imágenes se almacenan en MinIO. **Copiar SQLite no respalda las fotografías.** Tampoco se debe renombrar, mover o borrar manualmente un archivo dentro del volumen de MinIO: los objetos pueden incluir metadatos y fragmentos internos.

Las rutas actuales de SQLite, MinIO y `staticfiles/` se conservaron durante la reorganización porque los servicios y sincronizadores ya las utilizan. Cambiarlas requiere actualizar esas dependencias y realizar una migración planificada.

GitHub contiene el código, las migraciones y la configuración versionable. El estado actual de la base, fotografías, `.env`, logs y dependencias **no se incorpora a los commits normales**. El historial antiguo contiene objetos LFS; un clon completo puede necesitar Git LFS. El historial no sustituye a un respaldo actualizado de producción.

## Requisitos e instalación local

El proyecto usa Django 5.2, SQLite, MinIO/S3 y las bibliotecas indicadas en `requirements.txt`. La VM fue verificada con Python 3.14; eso describe el entorno actual, no una certificación de compatibilidad para cualquier versión de Python o sistema operativo. Los procesos de consulta usan `fcntl` y señales de Unix, por lo que Linux es el entorno de referencia para ejecutar el sistema completo.

Para preparar un entorno independiente:

```bash
git clone git@github.com:yuchuariRBO/DashBoard_BZA.git bonanza
cd bonanza
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

Antes de iniciar, editar `.env`:

1. Establecer una `DJANGO_SECRET_KEY` propia y reemplazar todos los valores de ejemplo.
2. Usar `DEBUG=True` únicamente en desarrollo y ajustar hosts y orígenes locales.
3. Cambiar `DATABASE_NAME` a una ruta SQLite local propia; el ejemplo apunta a la VM de producción.
4. Ajustar `LOG_DIR` y `RUN_DIR` a rutas escribibles de este entorno, o eliminar esas dos variables para usar los valores predeterminados del proyecto.
5. Configurar un MinIO independiente, crear el bucket y completar sus credenciales antes de probar carga de archivos.
6. Mantener desactivadas o sin configurar las integraciones que no deban enviar correos, mensajes o consultas reales durante el desarrollo.

La configuración lee `.env` desde la raíz de `bonanza`; las variables ya definidas en el entorno tienen prioridad. No es necesario ejecutar `source .env` para usar los comandos de Django.

```bash
venv/bin/python inventario_bonanza/manage.py check
venv/bin/python inventario_bonanza/manage.py migrate
venv/bin/python inventario_bonanza/manage.py createsuperuser
venv/bin/python inventario_bonanza/manage.py runserver 127.0.0.1:8000
```

`createsuperuser` crea el acceso administrativo de Django. La organización y el `user_type` usados por los paneles de negocio deben asignarse explícitamente desde la administración correspondiente. Definir `GLOBAL_ADMIN_*` en el archivo de ejemplo no crea automáticamente ese usuario.

Gunicorn se utiliza en producción y debe estar instalado en el entorno que ejecute su unidad systemd; no está declarado en el `requirements.txt` actual. Las cargas con `ImageField` también requieren Pillow. Verificar esos requisitos en una instalación nueva y agregarlos al proceso de aprovisionamiento. Playwright requiere sus navegadores si se utiliza una fuente que los necesite; instalar solo los necesarios para esos conectores.

## Variables de entorno

El archivo [`.env.example`](.env.example) sirve como plantilla. Esta tabla distingue los valores consumidos por Django de los que sirven de referencia operativa.

| Grupo | Variables | Uso |
|---|---|---|
| Django | `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Clave, modo de ejecución, hosts y orígenes permitidos; las listas se separan con comas |
| SQLite | `DATABASE_ENGINE`, `DATABASE_NAME` | Motor y ruta; por defecto SQLite dentro de `inventario_bonanza/` |
| Archivos S3 | `MINIO_ENDPOINT_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`, `MINIO_REGION_NAME` | Backend de almacenamiento usado por Django; región predeterminada `us-east-1` |
| Servidor MinIO | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Credenciales del servidor cuando su unidad recibe estas variables; revisar la unidad efectiva |
| API de placas | `PLATE_LOOKUP_API_TOKEN` | Token de integración de consultas de placas |
| API de personas | `PERSON_LOOKUP_API_TOKEN` | Token de integración de consultas de personas |
| Sincronizador de galería | `FACE_GALLERY_API_TOKEN` | Token de acceso al feed de metadatos de personal |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS` | Configuración de notificaciones; los IDs se separan con comas |
| Correo | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Entrega SMTP; el remitente usa `EMAIL_HOST_USER` |
| Archivos operativos | `LOG_DIR`, `RUN_DIR` | Raíces de logs y bloqueos temporales |

`DATABASE_ADMIN_*`, `DATABASE_DESCRIPTION`, `GLOBAL_ADMIN_*`, `APP_URL`, `DJANGO_SERVICE`, `MINIO_SERVICE`, `NGINX_SITE`, `MINIO_CONSOLE_URL` y `MINIO_PERSON_PHOTO_PATH` aparecen como referencias en la plantilla, pero no son mecanismos automáticos de aprovisionamiento en los settings actuales. SQLite no utiliza usuario y contraseña de conexión. `MINIO_VOLUMES` y `MINIO_OPTS` solo tienen efecto si la unidad de MinIO los consume; la plantilla versionada usa argumentos explícitos en `ExecStart`.

Las alertas también cuentan con una pantalla de configuración y el modelo `TelegramAlertSettings`. Revisar [la guía de Fail2ban](docs/operations/fail2ban.md) antes de cambiar las acciones del servidor.

## Servicios de producción

| Unidad o componente | Función | Configuración de referencia |
|---|---|---|
| `bonanza-gunicorn.service` | Tres workers Django en `127.0.0.1:8000` | `deploy/systemd/bonanza-gunicorn.service` |
| Drop-in de Gunicorn | Destinos de logs y `UMask=0027` | `deploy/systemd/bonanza-gunicorn.service.d/logging.conf` |
| `bonanza-plate-lookup-drain.service` | Procesa la cola de placas | `deploy/systemd/bonanza-plate-lookup-drain.service` |
| `bonanza-plate-lookup-drain.timer` | Inicia o vigila el servicio de placas | `deploy/systemd/bonanza-plate-lookup-drain.timer` |
| `minio.service` | Almacenamiento local de objetos | `deploy/systemd/minio.service` |
| `nginx.service` | Proxy HTTPS y archivos estáticos | `deploy/nginx/` |
| `logrotate.timer` | Ejecuta la rotación del sistema | Regla del proyecto: `deploy/logrotate/bonanza` |
| `fail2ban.service` | Protección de acceso SSH y posibles alertas | `deploy/security/fail2ban/` |

El timer de placas usa `OnBootSec=30`, `OnUnitInactiveSec=60` y `AccuracySec=5`. No ejecuta una consulta cada minuto si el drenador anterior sigue activo. Los workers de personas también pueden iniciarse desde la aplicación; no se incluye una unidad systemd activa dedicada a personas en este despliegue.

Las unidades activas y sus drop-ins están en `/etc/systemd/system/`; las de `deploy/` son configuración revisable para esta VM, con rutas absolutas. No copiar todas las plantillas encima de una instalación existente sin comparar sus personalizaciones. Los ejemplos de operación con `sudo` asumen un administrador autorizado.

```bash
sudo systemctl is-active bonanza-gunicorn nginx minio
sudo systemctl status bonanza-plate-lookup-drain.timer --no-pager
sudo systemctl list-timers --all
sudo systemctl cat bonanza-gunicorn
sudo systemctl cat bonanza-plate-lookup-drain
```

Después de editar una unidad o drop-in, ejecutar `sudo systemctl daemon-reload` y reiniciar únicamente el servicio afectado. Cambiar un archivo versionado en `deploy/` no modifica por sí solo la configuración instalada en `/etc/`.

## Actualizar un despliegue existente

Primero revisar el estado local, la rama y los commits que se publicarán. Conservar un respaldo reciente de SQLite y MinIO antes de aplicar migraciones. Las pruebas deben ejecutarse con configuración independiente de producción cuando existan integraciones reales.

```bash
cd /root/bonanza
git status --short --branch
git pull --ff-only origin main
venv/bin/python inventario_bonanza/manage.py check
venv/bin/python inventario_bonanza/manage.py showmigrations gestion_personal
venv/bin/python inventario_bonanza/manage.py migrate --plan
```

Revisar el plan antes de aplicar cambios de esquema. Por ejemplo, la migración `0021_remove_certificate_verification` elimina la tabla del antiguo módulo de verificación de certificados. El historial de migraciones se conserva aunque una funcionalidad haya sido retirada.

Una vez revisado el plan y creado el respaldo:

```bash
sudo /root/bonanza/venv/bin/python inventario_bonanza/manage.py migrate --noinput
sudo /root/bonanza/venv/bin/python inventario_bonanza/manage.py collectstatic --noinput
sudo systemctl restart bonanza-gunicorn
sudo systemctl is-active bonanza-gunicorn nginx minio
curl --fail --silent --output /dev/null --write-out '%{http_code}\n' \
  https://bonanza.robio-ai.com/login/
```

Si cambió un worker persistente, reiniciar también su servicio en una ventana coordinada. Si cambió Nginx, validar con `sudo nginx -t` y después usar `sudo systemctl reload nginx`. No reiniciar MinIO ni otros servicios de forma rutinaria cuando sus configuraciones no cambiaron.

Las rutas bajo `/root/` y el archivo `.env` tienen permisos restringidos; algunos comandos de Django requieren `sudo` en esta VM. En una instalación nueva conviene definir un usuario de servicio y rutas de datos apropiadas para ese entorno. No relajar los permisos de `.env` para resolver una lectura denegada.

## Logs y rotación

| Archivo relativo a `logs/` | Contenido |
|---|---|
| `application/django.log` | Eventos generales de Django y la aplicación |
| `errors/errors.log` | Eventos de nivel `ERROR` o superior; pueden aparecer también en su categoría original |
| `security/security.log` | Eventos del logger `django.security`, incluidos rechazos de seguridad |
| `notifications/notifications.log` | Eventos de correo y Telegram |
| `lookups/people/people.log` | Eventos del procesamiento de consultas de personas |
| `lookups/people/worker.log` | Inicio del drenador y salida de sus subprocesos |
| `lookups/plates/plates.log` | Eventos del procesamiento de consultas de placas |
| `lookups/plates/worker.log` | Salida y errores de subprocesos de placas |
| `gunicorn/access.log` | Solicitudes recibidas por Gunicorn |
| `gunicorn/error.log` | Arranque, errores de Gunicorn y salida capturada |

Los archivos se crean cuando se emite su primer evento. Que una carpeta esté vacía no significa que el servicio esté fallando. Los registros históricos anteriores a la reorganización se conservaron en `application/django.log`; no se intentó clasificarlos retrospectivamente.

Django usa `WatchedFileHandler`, adecuado para la rotación externa sin hacer competir a los workers por renombrar archivos. La regla activa está en `/etc/logrotate.d/bonanza` y su fuente en `deploy/logrotate/bonanza`:

- Evaluación diaria y hasta 14 archivos rotados por log.
- Compresión con `delaycompress`.
- `maxsize 25M` evaluado cuando corre logrotate; no es un límite continuo del tamaño.
- Los logs de Gunicorn y `worker.log` usan `copytruncate` porque mantienen descriptores abiertos; esa técnica puede perder algunas líneas durante la copia y truncado.
- En la VM, los directorios de logs tienen grupo `robiotec` y permisos restrictivos; las unidades aplican `UMask=0027`.

```bash
sudo tail -f /root/bonanza/logs/application/django.log
sudo tail -f /root/bonanza/logs/errors/errors.log
sudo tail -f /root/bonanza/logs/gunicorn/error.log
sudo journalctl -u bonanza-plate-lookup-drain -n 100 --no-pager
sudo journalctl -u minio -n 100 --no-pager
sudo logrotate --debug /etc/logrotate.conf
```

Nginx mantiene sus logs en `/var/log/nginx/`. Los mensajes de systemd de MinIO y de los workers permanecen en el journal; no se duplican artificialmente dentro de `bonanza`. Los bloqueos están en `run/`, no en `logs/`, y no deben borrarse con procesos activos.

## Consultas externas y procesamiento

Las consultas de personas y placas persisten sus respuestas en tablas propias dentro de SQLite. Los conectores pueden devolver resultados parciales si una fuente falla, cambia su interfaz, exige autenticación o excede su tiempo de respuesta.

| Estado | Significado |
|---|---|
| `pending` | Solicitud registrada y pendiente de procesamiento |
| `running` | Consulta en ejecución |
| `completed` | Consulta completada |
| `completed_with_errors` | Resultado guardado con errores de alguna fuente |
| `failed` | Consulta fallida |

Los drenadores usan bloqueos exclusivos para evitar ejecuciones simultáneas incompatibles. Las consultas individuales reciben un timeout acotado. El drenador de placas puede recuperar registros `running` antiguos de acuerdo con `--stale-minutes`. Un proceso con `--limit 0` puede atender toda la cola de placas; no debe iniciarse de forma indiscriminada sobre producción.

Comandos de referencia — **ejecutan trabajo real y pueden contactar fuentes externas**:

```bash
venv/bin/python inventario_bonanza/manage.py lookup_plate ABC1234 --timeout-seconds 120
venv/bin/python inventario_bonanza/manage.py lookup_person 0102030405 --timeout-seconds 120
venv/bin/python inventario_bonanza/manage.py drain_plate_lookups --limit 10 --sleep 5
venv/bin/python inventario_bonanza/manage.py drain_person_lookups --limit 2 --sleep 2
```

Para consultar opciones sin ejecutar trabajo:

```bash
venv/bin/python inventario_bonanza/manage.py help drain_plate_lookups
venv/bin/python inventario_bonanza/manage.py help drain_person_lookups
```

## Rutas web y APIs

### Navegación principal

| Ruta | Función |
|---|---|
| `/login/`, `/logout/`, `/role_redirect/` | Sesión y redirección por perfil |
| `/global/dashboard/` | Administración global |
| `/global/organizaciones/`, `/global/usuarios/` | Organizaciones y cuentas |
| `/global/placas/`, `/global/consultas-personas/` | Consulta y revisión de resultados guardados |
| `/global/alertas/` | Configuración de alertas |
| `/rh/dashboard/`, `/rh/gestion/` | Tableros de RRHH |
| `/rh/personas/`, `/rh/alojamiento/`, `/rh/comedores/` | Personal y asignaciones |
| `/operador/dashboard/`, `/seguridad/dashboard/` | Operación y seguridad física |
| `/medico/dashboard/`, `/tecnico/dashboard/` | Módulos médico y técnico |
| `/server/`, `/server/api/` | Estado del servidor; requiere sesión y autorización |
| `/media-minio/<ruta>` | Entrega de archivos privados según permisos |

Las rutas disponibles no conceden por sí solas acceso: cada operación aplica sus validaciones de perfil y alcance. Ver [urls.py](inventario_bonanza/gestion_personal/urls.py) para el inventario completo.

### APIs de integración

| Método y ruta | Cabecera requerida | Variable configurada |
|---|---|---|
| `GET /api/plate-lookup/<placa>/` | `X-Plate-Lookup-Token` | `PLATE_LOOKUP_API_TOKEN` |
| `GET /api/person-lookup/<cedula>/` | `X-Person-Lookup-Token` | `PERSON_LOOKUP_API_TOKEN` |
| `GET /api/face-gallery/people/` | `X-Face-Gallery-Token` | `FACE_GALLERY_API_TOKEN` |

Sin token configurado o con cabecera incorrecta, las APIs devuelven `401` y `{"ok": false, "error": "unauthorized"}`. Los tokens son credenciales de integración globales, no sesiones de usuario ni permisos limitados automáticamente a una organización. El feed de galería recorre el personal y devuelve metadatos; no entrega los bytes de las fotografías.

Ejemplos con valores ficticios:

```bash
curl -H 'X-Plate-Lookup-Token: TOKEN_DE_INTEGRACION' \
  https://bonanza.robio-ai.com/api/plate-lookup/ABC1234/

curl -H 'X-Person-Lookup-Token: TOKEN_DE_INTEGRACION' \
  https://bonanza.robio-ai.com/api/person-lookup/0102030405/

curl -H 'X-Face-Gallery-Token: TOKEN_DE_INTEGRACION' \
  https://bonanza.robio-ai.com/api/face-gallery/people/
```

Las APIs de consulta responden con `ok` y `record`; los errores de validación incorporan `error`. `record.estado` contiene el estado del procesamiento. Las respuestas de personas incluyen identidad, totales judiciales y de citaciones, datos por fuente y `source_errors`; las de placas incluyen propietario, características del vehículo, datos normalizados y errores por fuente. Los campos completos se construyen en las funciones `_person_lookup_api_payload` y `_plate_lookup_api_payload` de `views.py`.

Si no hay un resultado reutilizable, un GET de consulta **puede registrar una solicitud y lanzar trabajo en segundo plano**. No usar esos endpoints para una comprobación de salud sin efectos. Un resultado en estado `pending` o `running` no equivale a una consulta terminada; los resultados guardados se reutilizan según la lógica actual, sin prometer una actualización automática por antigüedad.

## Respaldos y recuperación

Un respaldo completo debe contemplar tres conjuntos: **SQLite**, **objetos de MinIO** y **configuración necesaria para recuperar la instalación**, incluidas las credenciales almacenadas de forma segura. Git cubre el código; no reemplaza ninguno de esos respaldos operativos.

### Copias locales encontradas

| Archivo en `/root/bonanza-backups/` | Fecha | Alcance |
|---|---|---|
| `db.sqlite3.backup-20260822-hr-requirements` | 22 de agosto de 2026 | Copia histórica de SQLite, aproximadamente 72 MiB |
| `db.sqlite3.before-reorganization-20261108` | 8 de noviembre de 2026 | Copia consistente de SQLite previa a la reorganización, aproximadamente 107 MiB |

Estas copias no incluyen las fotografías de MinIO. La copia temporal del código en `/tmp/bonanza-before-reorganization/` se creó para la intervención y puede desaparecer al limpiar temporales. No se encontró una programación automática de respaldo de la plataforma en las tareas revisadas; las copias locales tampoco protegen frente a la pérdida completa del disco.

### Ejemplo de respaldo consistente de SQLite

Ejecutar con un usuario que pueda leer la base y escribir en el directorio de respaldos. El ejemplo usa la ruta de producción actual; adaptarla si cambió `DATABASE_NAME`. La API de backup de SQLite permite obtener una copia consistente sin copiar a ciegas un archivo abierto.

```python
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3

source = Path('/root/bonanza/inventario_bonanza/db.sqlite3')
backup_dir = Path('/root/bonanza-backups')
backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
destination = backup_dir / f'db-{stamp}.sqlite3'
descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(descriptor)

with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as current:
    with sqlite3.connect(destination) as copied:
        current.backup(copied)
        result = copied.execute('PRAGMA quick_check').fetchone()[0]
        if result != 'ok':
            raise RuntimeError(f'La copia requiere revisión: {result}')
print(destination)
```

### Fotografías, documentos y restauración

Para respaldar objetos puede usarse una herramienta S3 autorizada que preserve las claves de los objetos. Si se decide copiar el **volumen completo** de MinIO a nivel de archivos, detener las escrituras de Django, workers y sincronizadores externos, detener MinIO y copiar el volumen completo con sus metadatos en una ventana coordinada. Una copia de carpetas mientras hay escrituras no debe darse por consistente.

Conservar varias fechas y al menos una copia externa al servidor. Las credenciales y los respaldos de personal requieren acceso restringido. La restauración debe probarse primero en un entorno independiente:

1. Elegir una copia compatible de base, objetos y configuración.
2. Comprobar integridad de SQLite y disponibilidad de los objetos referenciados.
3. Preparar la versión de código y esquema correspondiente.
4. Restaurar en una ubicación separada y validar usuarios, registros y fotografías.
5. Coordinar el cambio de producción y el tratamiento de datos generados después de la copia.

Restaurar una base antigua sobre producción sustituye su estado por el de esa fecha. No ejecutar una restauración únicamente para recuperar espacio ni usar `migrate` como sustituto de recuperar datos.

## Pruebas y validación

Las pruebas se organizan en `gestion_personal/tests/`. Cubren navegación y perfiles, aislamiento, archivos privados, consultas guardadas, identidad, errores públicos, carga de conectores y rutas de logging. Durante la reorganización del 8 de noviembre de 2026 se aprobaron **88 pruebas** con base temporal.

```bash
venv/bin/python inventario_bonanza/manage.py check
venv/bin/python inventario_bonanza/manage.py makemigrations --check --dry-run
venv/bin/python inventario_bonanza/manage.py test gestion_personal --noinput
git diff --check
```

Ejecutar preferiblemente en un entorno de pruebas, con configuración e integraciones propias. Django crea una base de pruebas separada; no definir su destino como la base activa. `LOG_DIR` y `RUN_DIR` pueden apuntarse a directorios temporales para evitar mezclar los registros y bloqueos de pruebas con producción.

Comprobaciones de servicio sin lanzar consultas externas:

```bash
sudo systemctl is-active bonanza-gunicorn nginx minio
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://bonanza.robio-ai.com/login/
curl --fail http://127.0.0.1:9000/minio/health/live
sudo nginx -t
sudo logrotate --debug /etc/logrotate.conf
```

La página de login respondió `200` y el endpoint local de salud de MinIO respondió `200` en la verificación de la reorganización. Las pruebas automatizadas no equivalen a una auditoría completa de infraestructura ni garantizan la disponibilidad de fuentes externas.

## Diagnóstico de problemas

| Síntoma | Revisar primero |
|---|---|
| Nginx devuelve `502` o `503` | Estado de `bonanza-gunicorn`, `logs/gunicorn/error.log`, puerto local 8000 y journal |
| Django no puede leer `.env` | Usuario efectivo y permisos; usar el usuario autorizado sin publicar el archivo |
| Fotografías no aparecen | Salud de MinIO, credenciales del backend, bucket y referencias guardadas; comprobar también sesión y organización |
| Una consulta queda pendiente | Estado del timer y drenador, `logs/lookups/`, cola visible en el panel y procesos activos |
| Una fuente devuelve error parcial | `source_errors`, conectividad y cambios de esa fuente; no borrar el resultado guardado para diagnosticar |
| API devuelve `401` | Variable de token configurada, cabecera correcta y servicio reiniciado tras un cambio de entorno |
| Formulario devuelve `403` CSRF | Origen HTTPS, `CSRF_TRUSTED_ORIGINS`, cookies y cabecera de proxy |
| Faltan CSS o imágenes del sitio | `collectstatic`, ruta `staticfiles/`, alias y permisos de Nginx |
| La VM se queda sin espacio | `df -h`, tamaños por directorio y logs; proteger SQLite y el volumen MinIO |

```bash
df -h /
sudo du -h --max-depth=1 /root/bonanza
sudo journalctl -u bonanza-gunicorn -n 100 --no-pager
sudo journalctl -u bonanza-plate-lookup-drain -n 100 --no-pager
sudo journalctl -u minio -n 100 --no-pager
```

## Mantenimiento y seguridad

- Mantener `.env`, los tokens y los respaldos de personal fuera de los commits. No incluir credenciales reales en ejemplos, incidencias o logs compartidos.
- No borrar `db.sqlite3`, `MinIO/`, migraciones, `venv/` ni `staticfiles/` como limpieza rutinaria: son datos o componentes utilizados por la instalación.
- Limpiar únicamente cachés regenerables y logs antiguos mediante sus mecanismos de retención. Conservar los bloqueos mientras haya procesos activos.
- El acceso a `/media-minio/` pasa por Django; las rutas de objetos no son una autorización por sí mismas. La configuración versionada bloquea la entrega directa de `/media/` desde Nginx.
- Los puertos locales de MinIO son 9000 y 9001. El proxy S3 de referencia usa 9443 para un sincronizador autorizado; revisar Nginx y el firewall efectivos antes de cambiar esa exposición.
- Las configuraciones de SSH, VPN y Fail2ban están en `deploy/security/`. Las reglas activas deben inspeccionarse en el servidor; la existencia de un script de cambio no significa que ya se haya ejecutado.
- Los scripts de `deploy/scripts/` modifican configuración y, en algunos casos, ejecutan migraciones o reinician servicios. Leerlos antes de ejecutarlos; no forman parte del arranque normal del dashboard.
- No revertir una migración o un respaldo sobre producción sin evaluar los datos que se perderían. Los cambios de esquema y el código deben mantenerse compatibles.

## Documentación complementaria

- [Arquitectura, estructura y verificación de la reorganización](docs/architecture.md).
- [Auditoría de septiembre y decisiones de aislamiento](docs/audits/2026-09-24.md).
- [Páginas de error y configuración de seguridad](docs/operations/errors-and-security.md), documento histórico con el alcance de aquella intervención.
- [Alertas de Fail2ban por Telegram](docs/operations/fail2ban.md).
- [Configuración central de logging](inventario_bonanza/inventario_bonanza/logging_config.py).
- [Servicios systemd](deploy/systemd/) y [regla de rotación](deploy/logrotate/bonanza).
- [Plantilla de variables de entorno](.env.example).
