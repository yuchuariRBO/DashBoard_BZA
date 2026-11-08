"""Resolve a display name from stored data without guessing a litigant's identity."""
import re
import unicodedata


def clean_name(value):
    if not isinstance(value, str):
        return ''
    value = ' '.join(value.split())
    if value.casefold() in {'', '-', '---', 'n/a', 'null', 'none', 'sin nombre', 'no disponible'}:
        return ''
    return value


def key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).lower() if c.isalnum())


def identifier(value):
    if not isinstance(value, str):
        return ''
    return re.sub(r'[\s-]', '', value)


def judicial_name(data, cedula):
    """Only accept same-object name/ID pairs; conflicting identities remain unresolved."""
    target = identifier(cedula)
    if not target:
        return ''
    candidates = {}
    stack = [data]
    generic_ids = ('cedula', 'identificacion', 'numeroidentificacion', 'identificacionlitigante', 'cedulalitigante')
    generic_names = ('nombrecompleto', 'nombrescompletos', 'nombrelitigante', 'nombreslitigante', 'nombresapellidos', 'apellidosnombres', 'nombre', 'nombres')
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            values = {key(k): v for k, v in item.items()}
            pairs = [(generic_ids, generic_names)]
            for role in ('actor', 'demandado', 'procesado', 'denunciado', 'litigante'):
                pairs.append(((f'cedula{role}', f'identificacion{role}', f'numeroidentificacion{role}'),
                              (f'nombre{role}', f'nombres{role}', f'nombrecompleto{role}')))
            for ids, names in pairs:
                if any(identifier(values.get(field)) == target for field in ids):
                    for field in names:
                        name = clean_name(values.get(field))
                        if name:
                            # Never concatenate a different nested person's name.
                            if field == 'nombres' and clean_name(values.get('apellidos')):
                                name = clean_name(values['apellidos']) + ' ' + name
                            candidates[key(name)] = name
                            break
            stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
    return next(iter(candidates.values())) if len(candidates) == 1 else ''


def stored_identity(record):
    existing = clean_name(record.nombre_completo)
    if existing:
        return {'name': existing, 'source': ''}
    normalized = record.normalized_data if isinstance(record.normalized_data, dict) else {}
    name = clean_name(normalized.get('nombre_completo'))
    if name:
        return {'name': name, 'source': 'Consulta guardada'}
    for label, payload, field in (
        ('SRI', record.sri_data, 'nombre_completo'),
        ('ANT', record.ant_data, 'nombre_completo'),
        ('SRI · RUC', normalized.get('sri_ruc_natural'), 'razon_social'),
    ):
        if not isinstance(payload, dict):
            continue
        source_id = payload.get('cedula') or payload.get('identificacion')
        if source_id and identifier(source_id) != identifier(record.cedula):
            continue
        name = clean_name(payload.get(field))
        if name:
            return {'name': name, 'source': label}
    name = judicial_name(record.funcion_judicial_data, record.cedula)
    if name:
        return {'name': name, 'source': 'Función Judicial · cédula coincidente'}
    return {'name': '', 'source': ''}
