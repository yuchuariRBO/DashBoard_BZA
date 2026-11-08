"""Presentation of already stored lookup results; never queries external sources."""


def mapping(value):
    return value if isinstance(value, dict) else {}


def scalar(value):
    return str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ''


def case_card(item):
    item = mapping(item)
    fields = (
        ('Número de proceso', ('idJuicio', 'numeroProceso', 'numeroCausa', 'numeroJuicio', 'numero')),
        ('Fecha de ingreso', ('fechaIngreso', 'fechaRegistro', 'fecha')),
        ('Materia', ('nombreMateria', 'materia')),
        ('Acción o asunto', ('nombreDelito', 'delito', 'nombreTipoAccion', 'tipoAccion', 'asunto')),
        ('Dependencia judicial', ('nombreJudicatura', 'nombreDependencia', 'judicatura', 'dependencia')),
        ('Estado informado', ('estadoActual', 'estado')),
    )
    details = []
    for label, keys in fields:
        value = next((scalar(item[key]) for key in keys if scalar(item.get(key))), '')
        if value:
            details.append({'label': label, 'value': value})
    return details


def person_lookup_presentation(record):
    if not record:
        return {}
    fj = mapping(record.funcion_judicial_data)
    errors = mapping(record.source_errors)
    sections = []
    for role, title, description, total in (
        ('actor', 'Procesos como actor', 'Procesos en los que figura como parte actora.', record.procesos_actor_total),
        ('demandado', 'Procesos como demandado', 'Procesos en los que figura como parte demandada.', record.procesos_demandado_total),
    ):
        raw = fj.get('procesos_' + role)
        items = raw if isinstance(raw, list) else []
        failed = bool(errors.get('funcion_judicial') or fj.get('error'))
        available = isinstance(raw, list) and not failed
        sections.append({'id': role, 'title': title, 'description': description,
                         'total': total if available else None, 'cards': [case_card(item) for item in items],
                         'shown': len(items), 'partial': bool(items) and (failed or total > len(items)),
                         'unavailable': not available})
    supa = mapping(mapping(record.normalized_data).get('supa'))
    tables = []
    raw_tables = supa.get('tablas')
    if isinstance(raw_tables, list):
        for table in raw_tables:
            if not isinstance(table, list):
                continue
            rows = [[scalar(cell) for cell in row] for row in table if isinstance(row, list)]
            rows = [row for row in rows if row]
            if rows:
                width = max(map(len, rows))
                padded = [row + [''] * (width - len(row)) for row in rows]
                tables.append({'headers': padded[0], 'rows': padded[1:]})
    supa_unavailable = bool(errors.get('supa')) or not isinstance(raw_tables, list)
    return {'judicial_sections': sections, 'supa_tables': tables,
            'supa_unavailable': supa_unavailable,
            'supa_total': supa.get('registros_total') if not supa_unavailable else None}
