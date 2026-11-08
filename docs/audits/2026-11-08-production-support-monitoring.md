# Despliegue de mesa de ayuda y monitoreo — 8 de noviembre de 2026

Despliegue autorizado expresamente por el usuario y ejecutado en la VM de Bonanza. La mesa de ayuda, el Centro de monitoreo y los cinco dashboards de Grafana están activos en HTTPS.

## Cambios aplicados

- Instalado `prometheus-client==0.25.0` en el virtualenv existente; el resto de dependencias se conservó.
- Respaldo consistente mediante SQLite Backup API y `quick_check` correcto: `/var/backups/bonanza/support-monitoring-20261108T182457Z/database.sqlite3`. En el mismo directorio privado se conservaron `.env`, configuración de Nginx, drop-ins de Gunicorn y diferencias del código. No se copiaron objetos de MinIO, que no fueron modificados.
- Aplicadas `support.0001_initial`, `support.0002_defaults`, `observability.0001_initial` y `observability.0002_default_rules`.
- Recopilados tres estáticos nuevos/actualizados y conservados los 129 restantes; añadida versión a CSS y escáner QR para renovar la caché de navegadores.
- Carpeta de adjuntos: `/var/lib/bonanza-support/`, privada y fuera de medios públicos.
- Instalados servicios nativos `bonanza-prometheus`, `bonanza-grafana`, `bonanza-alertmanager` y temporizador `bonanza-monitoring-sample.timer`. Se ejecutan con cuenta de sistema sin login, excepto el comando Django que utiliza la misma identidad de servicio que la aplicación existente.
- Prometheus 3.16.0, Grafana 13.3.0 y Alertmanager 0.34.2 escuchan solo en loopback. Prometheus limita retención a 15 días/512 MB. Configuración y secretos están fuera del repositorio, en `/etc/bonanza-observability/`.
- Gunicorn conserva tres workers síncronos y sus destinos de logs. El nuevo drop-in configura métricas multiproceso y elimina únicamente los archivos `.db` de su directorio de métricas antes de un arranque completo.
- Nginx sirve `/grafana/` con `auth_request` a Django; los encabezados de identidad/rol se calculan después de verificar la sesión. `robiotec` recibe Admin; usuarios con permiso técnico sin administración reciben Viewer. Las solicitudes anónimas no obtienen datos y los usuarios normales reciben 403. Grafana confía exclusivamente en el proxy local.
- Nginx restringe el endpoint de métricas a loopback; Prometheus lo consulta por HTTPS con token y certificado verificado. El token no se expone en enlaces ni en archivos versionados.
- Configurado un sondeo de salud de MinIO local y evaluación de alertas cada minuto. No se configuraron destinatarios ni envíos externos. Los objetivos SLA permanecen deshabilitados hasta que el administrador los apruebe.

Django estuvo detenido brevemente durante migraciones/recopilación y volvió a arrancar con el nuevo código. MinIO y el resto de procesos de consulta continuaron funcionando. Se corrigió el permiso de recorrido del directorio privado de configuración antes de dar por terminada la puesta en marcha; los servicios finales quedaron en ejecución estable.

## Verificación

- **135 pruebas Django correctas** en configuración aislada antes del despliegue; cinco comprobaciones específicas adicionales de plantillas y autorización correctas.
- `manage.py check`, plan de migraciones, `nginx -t`, `promtool check config`, reglas y `amtool check-config`: correctos.
- En HTTPS, administrador `robiotec`: HTTP 200 en solicitudes propias, creación, cola general, estadísticas, configuración, Centro de monitoreo y reglas.
- Un usuario normal existente: HTTP 200 en mesa de ayuda y 403 en Centro de monitoreo y API Grafana.
- Grafana identifica al administrador como `robiotec` mediante su sesión Django y devuelve los cinco dashboards esperados. El acceso anónimo no devuelve su API de datos.
- Tres recursos estáticos comprobados: HTTP 200.
- Prometheus: targets `bonanza` y `prometheus` en `up`, sin errores de scrape; métrica de tres workers vivos correcta.
- Confirmadas las cuatro migraciones, siete categorías iniciales y políticas SLA inicialmente deshabilitadas.
- No se crearon tickets de prueba en la base real. Las sesiones temporales de verificación se eliminaron al terminar; no se cambiaron contraseñas de usuarios.
- Servicios finales activos: Gunicorn, Nginx, MinIO, Prometheus, Grafana y Alertmanager; muestreador habilitado mediante timer.

Registro de despliegue: `/var/log/bonanza-support-monitoring-deploy.log`. Resultado de verificación: `/var/log/bonanza-production-verification.json`. Ambos quedan fuera del repositorio.

## Operación

- Usuarios: [Mesa de ayuda](https://bonanza.robio-ai.com/soporte/).
- Administrador: [Tickets reportados](https://bonanza.robio-ai.com/soporte/?team=1) y [Centro de monitoreo](https://bonanza.robio-ai.com/observabilidad/).
- Grafana: [dashboards](https://bonanza.robio-ai.com/grafana/), mediante la sesión administrativa del sitio.

```bash
sudo systemctl status bonanza-gunicorn bonanza-prometheus bonanza-grafana bonanza-alertmanager
sudo systemctl status bonanza-monitoring-sample.timer
sudo journalctl -u bonanza-monitoring-sample.service -n 30 --no-pager
```

La carpeta de adjuntos privados y los datos/configuración de Grafana deben incorporarse a los respaldos recurrentes. Las credenciales permanecen en archivos de configuración protegidos; no copiarlas a GitHub. El exportador de infraestructura opcional y las métricas de un motor de base de datos de servidor no se desplegaron; SQLite continúa siendo el motor actual.

## Recuperación

Conservar primero cualquier ticket o archivo creado después del despliegue. No restaurar automáticamente la copia SQLite sobre datos recientes. Para retirar la ampliación, coordinar una ventana, respaldar el estado actual y recuperar conjuntamente el código anterior, configuración, esquema y archivos pertinentes. La copia de `.env`, Nginx y drop-ins permite revisar los cambios previos. No es necesario reiniciar o restaurar MinIO para revertir estos módulos.
