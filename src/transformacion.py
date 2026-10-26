"""Variables analíticas por grupo, reutilizables para entradas individuales."""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


def percentil(values, p):
    s = sorted(Decimal(str(x)) for x in values)
    k = (len(s) - 1) * Decimal(str(p)); i = int(k)
    return s[i] + (s[min(i+1, len(s)-1)] - s[i]) * (k-i)


class AnaliticaFinal(BaseModel):
    model_config = ConfigDict(strict=True)
    monto_mxn: Decimal = Field(ge=0, allow_inf_nan=False)
    monto_analitico_mxn: Decimal = Field(ge=0, allow_inf_nan=False)
    monto_normalizado: float = Field(ge=0, le=1, allow_inf_nan=False)


def escalar_segmentar(registros, parametros=None):
    reference = parametros is not None
    params = {} if parametros is None else parametros
    if not reference:
        groups = {}
        for r in registros:
            groups.setdefault(r['fuente']+'|'+r['tipo_operacion'], []).append(r['monto_analitico_mxn'])
        for key, values in groups.items():
            params[key] = {'min': min(values), 'max': max(values), 'q1_3': percentil(values, Decimal(1)/3), 'q2_3': percentil(values, Decimal(2)/3)}
    candidates, rejected = [], []
    for r in registros:
        r = dict(r); value = Decimal(str(r['monto_analitico_mxn']))
        if r['tipo_operacion'] == 'CONSULTA_SALDO':
            r.update(monto_normalizado=0.0, segmento='BAJO'); candidates.append(r); continue
        info = params.get(r['fuente']+'|'+r['tipo_operacion'])
        if not info:
            rejected.append({'original_json': r, 'motivo': 'REFERENCIA_ESTADISTICA_INSUFICIENTE'}); continue
        lo, hi, a, b = (Decimal(str(info[k])) for k in ('min','max','q1_3','q2_3'))
        if lo == hi and reference and value != lo:
            rejected.append({'original_json': r, 'motivo': 'REFERENCIA_ESTADISTICA_INSUFICIENTE'}); continue
        scaled = (value-lo)/(hi-lo) if hi != lo else Decimal(0)
        r['fuera_rango_referencia'] = scaled < 0 or scaled > 1
        r['monto_normalizado'] = float(min(1,max(0,scaled)))
        r['segmento'] = 'BAJO' if value <= a else 'MEDIO' if value <= b else 'ALTO'
        r['rango_constante'] = lo == hi
        AnaliticaFinal.model_validate({k:r[k] for k in AnaliticaFinal.model_fields})
        candidates.append(r)
    return {'candidatos':candidates,'rechazados':rejected,'parametros':params}
