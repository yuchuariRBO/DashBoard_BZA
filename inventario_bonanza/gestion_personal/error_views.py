"""Public error responses never include exception or request details."""
from django.http import HttpResponse, JsonResponse


def error_response(request, status):
    title = 'Página no disponible' if status < 500 else 'Servicio no disponible'
    message = 'No podemos abrir esta página. Vuelve al inicio para continuar.' if status < 500 else 'No podemos atender la solicitud en este momento. Inténtalo de nuevo más tarde.'
    if request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
        response = JsonResponse({'ok': False, 'error': title, 'message': message}, status=status)
    else:
        response = HttpResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#f2f5f8;color:#172b42;font:18px system-ui,sans-serif;display:grid;min-height:100vh;place-items:center}}main{{max-width:540px;margin:24px;padding:40px;background:white;border-radius:16px}}h1{{font-size:30px}}p{{line-height:1.6}}a{{display:inline-block;padding:12px 20px;background:#163a60;color:white;border-radius:8px;text-decoration:none}}</style></head>
<body><main><h1>{title}</h1><p>{message}</p><a href="/">Volver al inicio</a></main></body></html>''', status=status)
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['Referrer-Policy'] = 'no-referrer'
    response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    return response


def bad_request(request, exception=None):
    return error_response(request, 400)


def forbidden(request, exception=None):
    return error_response(request, 403)


def not_found(request, exception=None):
    return error_response(request, 404)


def server_error(request):
    return error_response(request, 500)


def csrf_failure(request, reason=''):
    return error_response(request, 403)
