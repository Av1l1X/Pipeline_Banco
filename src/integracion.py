"""Puente entre modelos de Leo y el esquema común de integración."""
from decimal import Decimal, ROUND_HALF_UP
from src.lectura import FIELDS
from src.persistence import _json_dumps, _source_fingerprint
from src.validation import validate_atm_record_detailed, validate_digital_record_detailed

TASA = Decimal('19.50')


def money(value):
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def rechazo(record, code, campo='', mensaje='', fase='INTEGRACION'):
    return {'record': record, 'reasons': [code], 'fase': fase,
            'detalles_errores': [{'codigo': code, 'campo': campo, 'descripcion': mensaje or code}]}


def normalizar(registros, fuente):
    candidates, rejected = [], []
    validate = validate_atm_record_detailed if fuente == 'ATM' else validate_digital_record_detailed
    for raw in registros:
        original = raw.get('original_json', raw)
        if not isinstance(original, dict) or '_fila_invalida' in original:
            rejected.append(rechazo(raw, 'ESTRUCTURA_INVALIDA')); continue
        if any(isinstance(v, str) and v.startswith('=') for v in original.values()):
            rejected.append(rechazo(raw, 'FORMULA_NO_ADMITIDA')); continue
        model, details = validate(original)
        if details:
            rejected.append({'record': raw, 'reasons': sorted({d['codigo'] for d in details}), 'detalles_errores': details, 'fase': 'VALIDACION'}); continue
        values = model.model_dump()
        origin = {}
        # Huella previa a imputar: conserva faltantes, normaliza valores presentes.
        for key in FIELDS[fuente]:
            value = original.get(key)
            origin[key] = None if value is None or (isinstance(value, str) and not value.strip()) else values.get(key, value)
        if fuente == 'ATM':
            amount, currency = values['monto_mxn'], 'MXN'
            identifier, account, when, status = (values[k] for k in ('id_transaccion', 'id_cuenta', 'fecha_hora', 'resultado'))
        else:
            amount, currency = values['amount'], values['currency']
            identifier, account, when, status = (values[k] for k in ('transfer_id', 'account_id', 'timestamp', 'status'))
        r = {**raw, **values, 'fuente': fuente, 'id_transaccion': identifier, 'id_cuenta': account,
             'fecha_hora': when, 'fecha': when.date().isoformat(), 'estado_operacion': status,
             'tipo_operacion': values.get('tipo_operacion', 'TRANSFERENCIA'), 'moneda_original': currency,
             'monto_original': amount, 'monto_mxn': money(amount * (TASA if currency == 'USD' else 1)) if amount is not None else None,
             'tasa_conversion': TASA if currency == 'USD' else Decimal(1), 'registro_origen': origin}
        if fuente == 'ATM' and r.get('comision_aplicada') is not None:
            r['comision_aplicada'] = money(r['comision_aplicada'])
        changes = []
        for key, value in values.items():
            before = original.get(key)
            if str(before) != str(value):
                changes.append({'campo': key, 'antes': before, 'despues': value, 'regla': 'NORMALIZACION'})
        if currency == 'USD':
            changes.append({'campo': 'monto_mxn', 'antes': amount, 'despues': r['monto_mxn'], 'regla': 'USD_MXN_19.50'})
        r['transformaciones'] = changes
        r['huella_origen'] = _source_fingerprint(r)
        candidates.append(r)
    return {'candidatos': candidates, 'rechazados': rejected}


def cruzar_catalogo(registros, catalogo):
    candidates, rejected = [], []
    for r in registros:
        account = catalogo.get(r['id_cuenta'])
        if account is None:
            rejected.append(rechazo(r, 'CUENTA_NO_REGISTRADA', 'id_cuenta')); continue
        candidates.append({**r, 'cuenta': account, 'estado_cuenta': account['estado_cuenta']})
    return {'candidatos': candidates, 'rechazados': rejected}
