# DashboardBZA

Aplicación Django para gestión de personal, accesos, visitantes, vehículos y controles internos.

## Estructura

- `inventario_bonanza/manage.py`: entrada de comandos Django.
- `inventario_bonanza/inventario_bonanza/`: configuración principal del proyecto.
- `inventario_bonanza/gestion_personal/`: aplicación de negocio.
- `inventario_bonanza/static/`: estáticos fuente versionables.
- `inventario_bonanza/media/`: archivos subidos localmente, no versionados.
- `inventario_bonanza/staticfiles/`: salida de `collectstatic`, no versionada.

## Configuración local

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python inventario_bonanza/manage.py migrate
venv/bin/python inventario_bonanza/manage.py runserver
```

## Variables de entorno

- `DJANGO_SECRET_KEY`
- `DEBUG`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
