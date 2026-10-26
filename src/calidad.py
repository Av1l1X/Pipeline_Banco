"""M1: perfilado inicial de calidad. No muta la entrada."""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter
from decimal import Decimal
from datetime import datetime
from typing import Any


def _tipo_observado(valor: Any) -> str:
    if valor is None:
        return "nulo"
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, int):
        return "int"
    if isinstance(valor, float):
        return "float"
    if isinstance(valor, Decimal):
        return "decimal"
    if isinstance(valor, datetime):
        return "datetime"
    if isinstance(valor, str):
        return "str"
    if isinstance(valor, (list, dict)):
        return "objeto"
    return type(valor).__name__


def _es_vacio(valor: Any) -> bool:
    return isinstance(valor, str) and valor.strip() == ""


def _top_categorias(valores: list[Any], k: int = 5) -> dict:
    if not valores:
        return {}
    if not all(isinstance(v, (str, int, bool)) for v in valores):
        return {}
    conteo = Counter(valores)
    return dict(conteo.most_common(k))


def perfilar(registros: list[dict], fuente: str) -> dict:
    """Perfila una lista de diccionarios crudos. No modifica los registros."""
    total = len(registros)
    campos: set[str] = set()
    for r in registros:
        campos.update(r.keys())

    metricas_por_campo: dict[str, dict] = {}
    for campo in sorted(campos):
        nulos = vacios = 0
        tipos: Counter[str] = Counter()
        valores_no_nulos: list[Any] = []
        for r in registros:
            v = r.get(campo)
            if v is None:
                nulos += 1
            elif _es_vacio(v):
                vacios += 1
            else:
                tipos[_tipo_observado(v)] += 1
                valores_no_nulos.append(v)
        metricas_por_campo[campo] = {
            "nulos": nulos,
            "vacios": vacios,
            "no_nulos": total - nulos - vacios,
            "pct_nulos": round(nulos / total * 100, 2) if total else 0.0,
            "pct_vacios": round(vacios / total * 100, 2) if total else 0.0,
            "tipos_observados": dict(tipos),
            "categorias_top": _top_categorias(valores_no_nulos),
        }

    serializados = [json.dumps(r, sort_keys=True, default=str) for r in registros]
    conteo = Counter(serializados)
    duplicados_exactos = sum(c - 1 for c in conteo.values() if c > 1)

    return {
        "fuente": fuente,
        "filas": total,
        "campos": len(campos),
        "duplicados_exactos": duplicados_exactos,
        "metricas_por_campo": metricas_por_campo,
    }


def guardar_perfilado(perfilado: dict, ruta: str | Path) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(perfilado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

def comparar_calidad(antes: dict, despues: dict, resumen: dict) -> dict:
    """Compara perfilados antes/después. Genera métricas para la fase de reporte (M4)."""
    return {
        "antes": {
            "filas": antes["filas"],
            "duplicados_exactos": antes["duplicados_exactos"],
            "campos_con_nulos": {
                c: m["nulos"] for c, m in antes["metricas_por_campo"].items() if m["nulos"] > 0
            },
        },
        "despues": {
            "filas": despues["filas"],
            "duplicados_exactos": despues["duplicados_exactos"],
            "campos_con_nulos": {
                c: m["nulos"] for c, m in despues["metricas_por_campo"].items() if m["nulos"] > 0
            },
        },
        "efecto_por_etapa": {
            "imputados": resumen.get("imputados", 0),
            "rechazados": resumen.get("rechazados", 0),
            "duplicados_omitidos": resumen.get("duplicados_omitidos", 0),
        },
    }