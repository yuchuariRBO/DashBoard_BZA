# Errores públicos y configuración de seguridad

Las respuestas 400, 403, 404 y 500 de Django usan mensajes genéricos sin URL solicitada, excepciones ni listas de rutas. Las API reciben JSON en los manejadores de error. Los rechazos CSRF tampoco muestran detalles. Las páginas de error no necesitan sesión, base de datos, archivos estáticos ni servicios externos. Conservan el código HTTP y evitan caché e inclusión en marcos.

Se retiraron mensajes de excepción de marcación rápida, estado, salida de visitantes, importación y exportación. La marcación rápida ahora devuelve HTTP 500 cuando falla internamente, sin traza al cliente. Las API existentes siguen requiriendo sus tokens; ocultar rutas no sustituye su autorización.

## Activación

1. Mantener `DEBUG=False` en la configuración real. Los manejadores personalizados de Django no sustituyen el modo de diagnóstico cuando DEBUG=True.
2. Reiniciar `bonanza-gunicorn` para cargar el código. No hay nuevas migraciones por este cambio.
3. Integrar los bloques de `nginx-errors.conf` en la configuración activa de Nginx. Es una propuesta basada en el archivo versionado; no debe sobrescribirse la configuración activa sin comparar dominios y certificados.
4. Ejecutar `sudo nginx -t` y, solo si es válido, `sudo systemctl reload nginx`.

La propuesta de Nginx desactiva la versión del servidor, oculta X-Powered-By, bloquea rutas de archivos ocultos y sirve `service_unavailable.html` para errores 500/502/503/504 generados por Nginx. El archivo debe ser legible por el usuario de Nginx. No intercepta respuestas de la aplicación para conservar errores JSON y estados de autenticación. No se aplicó ni validó contra la configuración activa desde esta sesión por falta de permisos.

## Límites

Estas medidas reducen la información revelada en errores; no eliminan la posibilidad de descubrir rutas ni constituyen una auditoría completa de seguridad. Siguen pendientes los hallazgos de aislamiento de visitantes, visitas programadas y resultados de consultas descritos en ../audits/2026-09-24.md. No se cambió la política de tokens ni se configuró limitación de solicitudes, que debe dimensionarse según los clientes reales y el proxy activo.

Referencias: https://docs.djangoproject.com/en/5.2/topics/http/views/#customizing-error-views y https://nginx.org/en/docs/http/ngx_http_core_module.html#error_page
