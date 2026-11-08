# Auditoría de implementación — 8 de noviembre de 2026

**Actualización posterior:** la ampliación fue desplegada por autorización explícita. El estado de producción y sus verificaciones están en [el informe de despliegue](2026-11-08-production-support-monitoring.md). Las referencias a tareas pendientes en este documento corresponden al cierre de la implementación previa al despliegue.

## Resultado

Implementados dos módulos Django: mesa de ayuda y Centro de monitoreo. Código integrado en la navegación y la autenticación existentes, con cuatro migraciones nuevas preparadas. No se aplicaron a producción, no se reiniciaron servicios existentes ni se instalaron unidades de sistema. Se conservaron las modificaciones anteriores de responsividad.

La arquitectura, los modelos, permisos, flujo de estados, objetivos SLA, métricas, reglas y pasos de instalación están descritos en [la guía operativa](../support-monitoring.md).

## Verificaciones realizadas

| Verificación | Resultado |
| --- | --- |
| `manage.py check --settings=inventario_bonanza.settings_test` | Sin incidencias. |
| `manage.py check --settings=inventario_bonanza.settings_observability_dev` | Sin incidencias. |
| `makemigrations --check --dry-run` | Sin diferencias pendientes. |
| Regresión Django: `gestion_personal.tests support observability` | **131 pruebas correctas**, incluidas 40 pruebas nuevas. SQLite y almacenamiento aislados, sin credenciales de producción. |
| Autorización y privacidad | Tickets ajenos denegados; alcance por organización; notas internas y sus archivos ocultos; permisos técnicos separados; CSRF activo. |
| Archivos | Formatos y tamaño validados; descargas autenticadas; `nosniff`; almacenamiento privado sin URL pública y con permisos 0600. |
| Concurrencia en tickets | Dos escrituras simultáneas con la misma versión: una confirmada y otra rechazada como conflicto; sin sobrescritura ni comentarios duplicados. |
| Instrumentación concurrente | 200 solicitudes sintéticas en ocho hilos: contadores coherentes y concurrencia final cero. |
| Multiproceso Prometheus | Dos procesos: suma de contadores y limpieza de gauges de workers finalizados correctas. |
| Costo de instrumentación | Microprueba de 1.000 invocaciones: 4.5 µs sin instrumentación y 22.5 µs instrumentadas por solicitud; diferencia aproximada 18 µs. No incluye el trabajo de vistas, red ni persistencia inicial de actividad. |
| Caché y muestreo | Instantánea repetida sin consultas adicionales; usuario ya muestreado sin nueva escritura SQL. |
| Navegador Chromium | **10 pantallas × 7 resoluciones = 70 comprobaciones**, sin desbordamiento horizontal general ni fallos del menú móvil. |
| Plantillas y estáticos | Compilación de las 50 plantillas existentes y 10 nuevas; recursos locales y CDN utilizados sin errores observados en el navegador. |
| Grafana real, en pruebas | **13.3.0** iniciado con datos temporales y credenciales generadas; cinco dashboards aprovisionados y API anónima rechazada con 401. |
| Prometheus real, en pruebas | **3.16.0**, scrape autenticado de Django correcto; consultas de todos los paneles aceptadas y consulta agrupada de Django operativa. |
| Gunicorn de pruebas | Dos workers observados; endpoint de métricas devuelve 403 sin autorización. |
| Concurrencia HTTP moderada | 40 solicitudes, cuatro clientes, dos workers: todas HTTP 200; promedio 15.84 ms, P95 observado 18.65 ms. Solo entorno aislado; no constituye certificación de capacidad. |
| Reglas Prometheus | Diez reglas válidas; `promtool test rules` pasó las pruebas de persistencia de caída de servicio, tickets críticos y fallos recurrentes. |
| Alertas Django | Persistencia, deduplicación, resolución, servicio afectado, ausencia de telemetría y deshabilitación verificadas. Sin transporte externo. |
| Alertmanager | `amtool` **0.34.2** validó la configuración; receptor sin destinos de envío. |
| Docker Compose | El binario Compose **5.7.0** validó `compose.yaml` con `config --quiet`. No hay daemon Docker instalado; los contenedores no se iniciaron. Grafana/Prometheus se verificaron como procesos nativos temporales equivalentes. |
| Calidad | Ruff en módulos nuevos (excluyendo RUF012 por las convenciones declarativas Meta de Django), formato y `git diff --check` correctos. |

Las siete resoluciones fueron 360×800, 390×844, 768×1024, 1024×768, 1366×768, 1920×1080 y 2560×1440. Se revisaron capturas de alta de tickets, detalle y Centro de monitoreo en móvil.

Los procesos temporales de Gunicorn, Grafana y Prometheus fueron detenidos después de comprobarlos. No quedan escuchando en los puertos de prueba 18000, 19091 y 13001. Sus bases y logs se guardaron bajo `/tmp/bonanza-observability-validation`; las capturas están en `/tmp/bonanza-new-modules-browser`.

## Límites y tareas de despliegue

- Falta la autorización y ejecución del despliegue: instalar la dependencia en el virtualenv apropiado, aplicar migraciones, recopilar estáticos, respaldar/incluir adjuntos privados y revisar configuración multiproceso y permisos.
- SLA configurables preparados pero deshabilitados inicialmente; el administrador debe aprobar sus objetivos. Se requieren asignación de agentes, configuración de Grafana y programación del muestreador.
- Los sondeos externos permanecen deshabilitados hasta configurar destinos autorizados. No se probaron APIs privadas reales, canales externos, MinIO de producción ni alertas enviadas a personas.
- SQLite carece de métricas de conexiones de servidor, pool y saturación global. Tampoco se miden transacciones completas, procesos systemd, reinicios por servicio o uso por bucket MinIO; estas extensiones necesitan instrumentación/exportadores apropiados. El exportador opcional de infraestructura está preparado, sin desplegar.
- No se certificó el comportamiento a gran escala. Las pruebas de concurrencia fueron pequeñas y aisladas; SQLite devuelve conflictos recuperables bajo escrituras simultáneas.
- La validación básica de archivos no reemplaza análisis antivirus. No hay política automática de borrado de tickets/adjuntos.
- Grafana conserva autenticación independiente; el enlace desde Django no constituye SSO. Revisar sus cuentas administrativas antes de exponerlo mediante un proxy autenticado.
- Los umbrales Django y Prometheus son configuraciones separadas, indicadas expresamente en la guía; no se sincronizan automáticamente.

## Archivos de esta ampliación

La lista excluye otros archivos modificados durante la tarea anterior de responsividad, salvo `base.html`, donde esta ampliación añadió la navegación de soporte y monitoreo.

- `.env.example`
- `.gitignore`
- `README.md`
- `deploy/observability/alertmanager.yml`
- `deploy/observability/compose.yaml`
- `deploy/observability/dashboards/database.json`
- `deploy/observability/dashboards/django.json`
- `deploy/observability/dashboards/general.json`
- `deploy/observability/dashboards/services.json`
- `deploy/observability/dashboards/support.json`
- `deploy/observability/grafana/provisioning/dashboards/bonanza.yaml`
- `deploy/observability/grafana/provisioning/datasources/prometheus.yaml`
- `deploy/observability/gunicorn.conf.py`
- `deploy/observability/prometheus/alerts.yml`
- `deploy/observability/prometheus/prometheus.yml`
- `deploy/observability/prometheus/rules.test.yml`
- `docs/support-monitoring.md`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/base.html`
- `inventario_bonanza/inventario_bonanza/settings.py`
- `inventario_bonanza/inventario_bonanza/settings_observability_dev.py`
- `inventario_bonanza/inventario_bonanza/settings_test.py`
- `inventario_bonanza/inventario_bonanza/urls.py`
- `inventario_bonanza/inventario_bonanza/wsgi_observability_dev.py`
- `inventario_bonanza/observability/__init__.py`
- `inventario_bonanza/observability/alerts.py`
- `inventario_bonanza/observability/apps.py`
- `inventario_bonanza/observability/management/__init__.py`
- `inventario_bonanza/observability/management/commands/__init__.py`
- `inventario_bonanza/observability/management/commands/sample_monitoring.py`
- `inventario_bonanza/observability/metrics.py`
- `inventario_bonanza/observability/middleware.py`
- `inventario_bonanza/observability/migrations/0001_initial.py`
- `inventario_bonanza/observability/migrations/0002_default_rules.py`
- `inventario_bonanza/observability/migrations/__init__.py`
- `inventario_bonanza/observability/models.py`
- `inventario_bonanza/observability/permissions.py`
- `inventario_bonanza/observability/prometheus.py`
- `inventario_bonanza/observability/signals.py`
- `inventario_bonanza/observability/snapshot.py`
- `inventario_bonanza/observability/templates/observability/dashboard.html`
- `inventario_bonanza/observability/templates/observability/rules.html`
- `inventario_bonanza/observability/tests.py`
- `inventario_bonanza/observability/urls.py`
- `inventario_bonanza/observability/views.py`
- `inventario_bonanza/support/__init__.py`
- `inventario_bonanza/support/apps.py`
- `inventario_bonanza/support/context_processors.py`
- `inventario_bonanza/support/forms.py`
- `inventario_bonanza/support/management/__init__.py`
- `inventario_bonanza/support/management/commands/__init__.py`
- `inventario_bonanza/support/migrations/0001_initial.py`
- `inventario_bonanza/support/migrations/0002_defaults.py`
- `inventario_bonanza/support/migrations/__init__.py`
- `inventario_bonanza/support/models.py`
- `inventario_bonanza/support/permissions.py`
- `inventario_bonanza/support/services.py`
- `inventario_bonanza/support/storage.py`
- `inventario_bonanza/support/templates/support/_filters.html`
- `inventario_bonanza/support/templates/support/_nav.html`
- `inventario_bonanza/support/templates/support/configuration.html`
- `inventario_bonanza/support/templates/support/create.html`
- `inventario_bonanza/support/templates/support/dashboard.html`
- `inventario_bonanza/support/templates/support/detail.html`
- `inventario_bonanza/support/templates/support/list.html`
- `inventario_bonanza/support/templates/support/notifications.html`
- `inventario_bonanza/support/tests.py`
- `inventario_bonanza/support/urls.py`
- `inventario_bonanza/support/views.py`
- `requirements.txt`

## Acceso de robiotec y reportes desde el centro

Se verificó por consulta de solo lectura que `robiotec` es administrador global activo, superusuario y sin organización asignada. La base actual todavía no tiene migraciones de `support` ni `observability`; los módulos no están activos en producción.

Se incorporaron el enlace lateral **Tickets reportados**, los diez reportes recientes en el Centro de monitoreo y acceso directo a la cola completa. Los asuntos y enlaces a casos solo se muestran con permisos de soporte; un observador técnico conserva únicamente los agregados. Cinco pruebas específicas y de navegación pasaron, junto con siete comprobaciones de resolución en Chromium para el centro actualizado, sin desbordamiento horizontal ni fallo del menú móvil.
