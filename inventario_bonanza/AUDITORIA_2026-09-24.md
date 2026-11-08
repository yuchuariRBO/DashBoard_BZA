# Auditoría — 24 de septiembre de 2026

## Resultado y alcance

64 pruebas aprobadas; sin discrepancias de migraciones ni errores en `git diff --check`. Se revisaron los ocho perfiles y el administrador limitado a organización: paneles, enlaces laterales, redirecciones y acceso GET a rutas sin parámetros. Se verificaron operaciones seleccionadas de contraseña, certificados, EPP y vehículos. Base de pruebas temporal; no se realizaron consultas externas de personas ni modificaciones de datos reales.

No equivale a certificar toda la plataforma: las rutas con identificadores y operaciones POST tienen cobertura selectiva. No se realizó prueba visual en navegador ni auditoría de infraestructura.

## Correcciones de esta auditoría

- Salida de vehículos limitada a la organización del operador.
- Asignación EPP: selector y validación limitados al personal de la organización.
- Retiro de botón de exportación de Seguridad Física que llevaba a una función exclusiva de RRHH.
- Pruebas de navegación, permisos y registros de certificados.

El acceso del administrador de organización a RRHH es intencional según las reglas actuales.

## Retiro posterior de certificados

La verificación de certificados fue retirada por solicitud del usuario: menú, formulario, vista, ruta, modelo y plantilla. La migración 0020 se conserva como historial; la migración 0021 elimina su tabla y los registros que contenga al aplicarse.

## Actualización del aislamiento — 25 de septiembre

Corregido en código: visitantes y visitas programadas tienen organización propia. Se filtran listados, exportación de visitantes, acciones por ID y notificaciones. Una visita ajena no puede completarse ni vincularse a un registro nuevo; el rechazo no crea visitantes. Las transacciones evitan completar dos veces la misma visita en bases con bloqueo de filas. Usuarios sin organización no pueden registrar ni leer visitantes de ámbito desconocido. El administrador del sistema conserva acceso global; el administrador de organización conserva su ámbito.

Las consultas de personas y placas se mantienen como base común entre empresas por decisión expresa del usuario. Los perfiles con permiso pueden consultar resultados guardados por otras organizaciones. Las fuentes externas siguen alimentando la base local. Esto no se considera un fallo de aislamiento bajo la política acordada.

El reporte diario consolidado se dirige solo a administradores del sistema activos con correo configurado. No se envían reportes reales durante las pruebas.

La migración 0022 agrega organización a visitantes y visitas programadas sin borrar datos. Los registros históricos quedan sin organización y fuera de las pantallas de usuarios de empresa hasta que se asigne su organización con información comprobada. No se infiere por cédula, nombre ni organización actual de quien los creó.

Pendiente independiente: corregir indicadores de ingresos y salidas del panel de seguridad; no forma parte del aislamiento.

## Producción

Gunicorn y Nginx están activos. El acceso disponible no permite leer los registros completos ni reiniciar el servicio. No se verificó el despliegue de los cambios ni se ejecutaron migraciones de producción.

Antes de publicar, revisar también los cambios preexistentes de alertas y su migración 0019, aplicar migraciones con configuración real y reiniciar Gunicorn. Pruebas de auditoría en `gestion_personal/test_navigation.py`.
