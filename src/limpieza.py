"""M3 y M4: imputación de faltantes y tratamiento de outliers con IQR."""
from __future__ import annotations
from statistics import median
from typing import Any

MIN_OBSERVACIONES = 5

CAMPOS_DETERMINISTAS = {
    "id_cajero": "DESCONOCIDO",
    "concept": "SIN_CONCEPTO",
}

def _es_nulo_o_vacio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")

def _es_numero_valido(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v == v and v > 0  # no NaN, positivo
    return False

def _clave_grupo(r: dict, campos_grupo: tuple[str, ...]) -> str:
    return "|".join(str(r.get(c) or "") for c in campos_grupo)


def imputar(registros: list[dict], parametros: dict | None = None) -> dict:
    """Imputa faltantes según las reglas (M3)."""
    parametros = parametros or {}
    parametros_calculados: dict[str, Any] = {}
    candidatos: list[dict] = []
    rechazados: list[dict] = []

    for pos, r in enumerate(registros, start=1):
        reg = dict(r)  # copia para no mutar
        cambios: list[dict] = []

        # 1) Deterministas (Cajero, Concepto)
        for campo, valor_defecto in CAMPOS_DETERMINISTAS.items():
            if _es_nulo_o_vacio(reg.get(campo)):
                antes = reg.get(campo)
                reg[campo] = valor_defecto
                cambios.append({"campo": campo, "antes": antes,
                                "despues": valor_defecto,
                                "regla": "DETERMINISTA"})

        # 2) Consulta de saldo -> monto 0
        if (reg.get("tipo_operacion") == "CONSULTA_SALDO"
                and _es_nulo_o_vacio(reg.get("monto_mxn"))):
            antes = reg.get("monto_mxn")
            reg["monto_mxn"] = 0
            cambios.append({"campo": "monto_mxn", "antes": antes, "despues": 0,
                            "regla": "CONSULTA_SALDO_CERO"})

        # 3) Mediana por grupo para monto
        if _es_nulo_o_vacio(reg.get("monto_mxn")) and reg.get("tipo_operacion") != "CONSULTA_SALDO":
            fuente = reg.get("fuente", "")
            if fuente == "ATM":
                campos_grupo = ("tipo_operacion", "estado_operacion")
            else:
                campos_grupo = ("moneda_original", "estado_operacion")
            
            clave = _clave_grupo(reg, campos_grupo)
            valores_grupo = [
                x.get("monto_mxn") for x in registros
                if _clave_grupo(x, campos_grupo) == clave
                and _es_numero_valido(x.get("monto_mxn"))
            ]
            
            if len(valores_grupo) >= MIN_OBSERVACIONES:
                med = median(valores_grupo)
                parametros_calculados[clave] = {
                    "mediana": med,
                    "tamano_grupo": len(valores_grupo),
                    "campos_grupo": campos_grupo,
                }
                reg["monto_mxn"] = med
                cambios.append({"campo": "monto_mxn", "antes": None,
                                "despues": med, "regla": "MEDIANA_GRUPO",
                                "grupo": clave})
            else:
                rechazados.append({
                    "posicion": pos,
                    "motivo": "SIN_BASE_PARA_IMPUTAR",
                    "detalle": f"Grupo {clave} tiene {len(valores_grupo)} observaciones",
                    "original_json": r,
                })
                continue

        reg["_cambios_imputacion"] = cambios
        candidatos.append(reg)

    return {
        "candidatos": candidatos,
        "rechazados": rechazados,
        "parametros": {**parametros, **parametros_calculados},
    }


# --- M4: OUTLIERS E IQR ---

def _cuartiles(valores: list[float]) -> tuple[float, float]:
    """Q1 y Q3 con interpolación lineal."""
    s = sorted(valores)
    n = len(s)

    def _percentil(p: float) -> float:
        if n == 1: return s[0]
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c: return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)

    return _percentil(0.25), _percentil(0.75)

def aplicar_iqr(registros: list[dict], parametros: dict | None = None) -> dict:
    """Calcula límites IQR y aplica capping a monto_analitico_mxn (M4)."""
    parametros = parametros or {}
    parametros_resultado: dict = {}

    # Agrupar elegibles por (fuente, tipo_operacion)
    grupos: dict[str, list[float]] = {}
    elegibles: list[tuple[int, dict]] = []
    
    for pos, r in enumerate(registros, start=1):
        es_consulta = r.get("tipo_operacion") == "CONSULTA_SALDO"
        imputado = any(c["regla"] == "MEDIANA_GRUPO" for c in r.get("_cambios_imputacion", []))
        valor = r.get("monto_analitico_mxn", r.get("monto_mxn"))
        
        if es_consulta or imputado or not _es_numero_valido(valor):
            elegibles.append((pos, r))
            continue
            
        clave = f"{r.get('fuente','')}|{r.get('tipo_operacion','')}"
        grupos.setdefault(clave, []).append(float(valor))
        elegibles.append((pos, r))

    limites: dict[str, dict] = {}
    for clave, vals in grupos.items():
        if len(vals) < MIN_OBSERVACIONES:
            limites[clave] = {"recorte": False, "motivo": "GRUPO_MENOR_A_5", "n": len(vals)}
            continue
        q1, q3 = _cuartiles(vals)
        iqr = q3 - q1
        if iqr == 0:
            limites[clave] = {"recorte": False, "motivo": "IQR_CERO", "q1": q1, "q3": q3, "n": len(vals)}
            continue
        
        lo, hi = max(0, q1 - 1.5 * iqr), q3 + 1.5 * iqr
        limites[clave] = {"recorte": True, "q1": q1, "q3": q3, "iqr": iqr,
                          "limite_inferior": lo, "limite_superior": hi, "n": len(vals)}
        parametros_resultado[clave] = limites[clave]

    candidatos = []
    for pos, r in elegibles:
        reg = dict(r)
        clave = f"{r.get('fuente','')}|{r.get('tipo_operacion','')}"
        info = limites.get(clave, {})
        valor = reg.get("monto_analitico_mxn", reg.get("monto_mxn"))
        
        if info.get("recorte") and _es_numero_valido(valor):
            v = float(valor)
            lo, hi = info["limite_inferior"], info["limite_superior"]
            if v < lo:
                reg["monto_analitico_mxn"] = lo
                reg["es_outlier"] = True
            elif v > hi:
                reg["monto_analitico_mxn"] = hi
                reg["es_outlier"] = True
            else:
                reg["monto_analitico_mxn"] = v
                reg["es_outlier"] = False
        candidatos.append(reg)

    return {"candidatos": candidatos, "parametros": {**parametros, **parametros_resultado}}