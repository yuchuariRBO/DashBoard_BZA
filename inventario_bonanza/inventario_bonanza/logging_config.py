"""Central logging routes. File rotation is owned by deploy/logrotate/bonanza."""
from pathlib import Path


def build_logging_config(log_dir):
    log_dir = Path(log_dir)
    routes = {
        'application': 'application/django.log',
        'errors': 'errors/errors.log',
        'security': 'security/security.log',
        'people': 'lookups/people/people.log',
        'plates': 'lookups/plates/plates.log',
        'notifications': 'notifications/notifications.log',
    }
    handlers = {'console': {'class': 'logging.StreamHandler'}}
    for name, relative in routes.items():
        path = log_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers[name] = {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': str(path),
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'delay': True,
        }
    handlers['errors']['level'] = 'ERROR'
    def route(handler):
        return {'handlers': ['console', handler, 'errors'], 'level': 'INFO', 'propagate': False}
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'verbose': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'}},
        'handlers': handlers,
        'root': {'handlers': ['console', 'application', 'errors'], 'level': 'INFO'},
        'loggers': {
            'django': route('application'),
            'django.security': route('security'),
            'gestion_personal': route('application'),
            'gestion_personal.person_lookup': route('people'),
            'gestion_personal.plate_lookup': route('plates'),
            'gestion_personal.management.commands.lookup_person': route('people'),
            'gestion_personal.management.commands.lookup_plate': route('plates'),
            'gestion_personal.services.notifications': route('notifications'),
        },
    }
