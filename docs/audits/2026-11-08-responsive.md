# Revisión de responsividad — 8 de noviembre de 2026

## Diagnóstico y alcance

Aplicación Django existente: 50 plantillas en `gestion_personal/templates`, de las cuales 48 heredan directamente de `gestion_personal/base.html`; las otras son la base y el parcial `global_admin/person_legal_details.html`. Se revisaron también `service_unavailable.html`, los recursos estáticos y la estructura de formularios, vistas y pruebas. Bootstrap **5.3.0-alpha1**, servido por CDN, se conserva sin actualizar. La base carga Font Awesome 6.0.0, jQuery 3.6.0 y `platform.css`. El dashboard del operador carga html5-qrcode 2.3.8 y `qr-scanner.js`.

Problemas principales: alturas rígidas dependientes de una cabecera de 66 px, recorte horizontal del panel principal, menú lateral completo en móviles, encabezados sin ajuste de línea, panel de identificación de 520 px en jornada mensual, seis barras mensuales con mínimos incompatibles con móviles y visor QR de tamaño fijo. La mayoría de las tablas ya tenían contenedor desplazable; las tablas de datos personales médicos no lo tenían. No se encontraron DataTables, gráficos canvas ni menús Bootstrap desplegables dentro de las tablas.

## Cambios

- Distribución con Flexbox y altura mínima dinámica: el documento crece con su contenido, sin ocultar globalmente los desbordamientos.
- Menú lateral Bootstrap Collapse por debajo de 992 px; permanece visible en escritorio. Conserva enlaces, permisos y estados activos, con controles ARIA.
- Encabezados y acciones permiten varias líneas; columnas y tarjetas pueden contraerse. Se conservan las clases Grid, colores, tipografía e iconos existentes.
- Tablas con desplazamiento local y acceso por teclado. Un único módulo compartido prepara las tablas iniciales y las añadidas dinámicamente; respeta los paneles especiales de jornada mensual.
- Jornada mensual: columnas de identificación más compactas en tamaños intermedios; en móviles se desplaza el conjunto completo, manteniendo nombres, cargos, días y controles disponibles. El ancho fijo de los días se conserva dentro del área desplazable para mantener la edición alineada.
- Los adornos de tarjetas de colores dejan pasar los clics; antes interceptaban el botón Registrar del operador en la prueba móvil.
- Gráfico de barras CSS sin mínimo rígido por mes; se adapta sin JavaScript de redimensionamiento. QR calcula su área de lectura desde las dimensiones del visor; no cambia dispositivos, fuentes ni comunicación.
- Modales limitados al alto dinámico disponible, cuerpo desplazable y formularios internos flexibles para mantener visibles los pies. Botones táctiles de al menos 44 px donde corresponde.
- Corrección de una expresión Django inválida preexistente (`edad.split(...)`) en el detalle médico: se muestra el resultado del filtro `timesince`, sin modificar la lógica de negocio.

No se modificaron modelos, migraciones, endpoints, autenticación, permisos, configuración de producción ni dependencias de la aplicación.

## Validación

- `python manage.py check`: el intento con configuración habitual quedó impedido por la falta de permiso de lectura de `.env`. La ejecución posterior, con configuración temporal aislada, pasó sin incidencias.
- **63 pruebas correctas**: `gestion_personal.tests.test_navigation`, `gestion_personal.tests.test_core` y `gestion_personal.tests.test_responsive`. SQLite temporal en memoria, almacenamiento temporal y registros en `/tmp`; sin acceso a la base de producción.
- Compilación de las **50 plantillas**, comprobación de los controles y enlaces del menú y localización de CSS, JavaScript y logo mediante los buscadores de estáticos de Django.
- Chromium/Playwright: **17 páginas × 7 resoluciones = 119 comprobaciones**, sin desbordamiento horizontal del documento ni del panel principal. Se comprobó apertura y cierre del menú móvil en las páginas autenticadas. Resoluciones: 360×800, 390×844, 768×1024, 1024×768, 1366×768, 1920×1080 y 2560×1440.
- Páginas representativas: login, dashboards de todos los roles (incluido administrador con organización), gestión integral, cumpleaños, alta y listado de personas, jornada mensual, alojamiento y comedores. Renderizadas con Django Test Client y datos de prueba; Chromium sirvió sus recursos locales y obtuvo los recursos CDN originales, sin errores HTTP externos.
- Inspección visual de capturas móviles de login, gestión integral, jornada mensual y modal de comedores; también se generaron capturas de escritorio.
- **12 comprobaciones adicionales en Chromium** sobre alojamiento, comedores, operador y jornada mensual, a 360×800, 390×400 y 1024×768: apertura/cierre de modales, pies visibles incluso en ventana de poca altura y desplazamiento hasta los últimos días de la jornada; sin fallos.
- `git diff --check`: correcto.

## Límites

Las comprobaciones del navegador usaron datos de prueba y páginas representativas; no equivalen a probar todas las combinaciones de registros reales. No se verificaron captura física de cámara, lectura de QR real, servicios externos de consulta ni infraestructura de estáticos de producción. Las capturas y registros de esta sesión están en `/tmp/bonanza-responsive-browser` y `/tmp/bonanza-responsive-*.log`.

## Archivos modificados

- `inventario_bonanza/gestion_personal/templates/gestion_personal/admin/dashboard_admin.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/admin/editar_visita_programada.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/admin/personal_area.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/admin/registros_por_fecha.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/admin/visitas_programadas.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/base.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/dashboard.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/organization_detail.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/organization_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/organization_list.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/person_lookup.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/plate_lookup.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/records.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/server_status.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/telegram_alerts.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/user_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/global_admin/user_list.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/dashboard_medico.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/medical_checkup_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/medical_consultation_detail.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/medical_consultation_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/person_detail.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/person_list.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/medico/vacation_checkup.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/operador/dashboard_operador.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/operador/registros_diarios.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/operador/retorno_vacaciones.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/accommodation_rack.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/dashboard_rrhh.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/dining_hall_management.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/export_attendance.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/hr_management_dashboard.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/import_excel.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/monthly_workday_template.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/person_confirm_delete.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/person_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/person_list.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/registrar_sancion.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/vacation_form.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/rh/vacation_list.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/seguridad/dashboard_seguridad.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/seguridad/registros_por_fecha.html`
- `inventario_bonanza/gestion_personal/templates/gestion_personal/tecnico/dashboard_tecnico.html`
- `inventario_bonanza/gestion_personal/tests/test_responsive.py`
- `inventario_bonanza/static/css/platform.css`
- `inventario_bonanza/static/js/qr-scanner.js`
- `inventario_bonanza/static/js/responsive.js`
