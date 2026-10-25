"""M2: separación de duplicados exactos y detección de conflictos."""
from __future__ import annotations
import json
from collections import defaultdict
from typing import Any


def _clave_exacta(r: dict) -> str:
    """Serializa el dict para comparar contenido exacto."""
    return json.dumps(r, sort_keys=True, default=str)


def separar_exactos(registros: list[dict]) -> dict:
    """Conserva la primera aparición exacta; el resto va a omitidos."""
    vistos: dict[str, int] = {}
    unicos: list[dict] = []
    omitidos: list[dict] = []
    
    for pos, r in enumerate(registros, start=1):
        clave = _clave_exacta(r)
        if clave in vistos:
            omitidos.append({
                "posicion": pos,
                "referencia_conservada": vistos[clave],
                "motivo": "DUPLICADO_EXACTO",
                "original_json": r,
            })
        else:
            vistos[clave] = pos
            unicos.append(r)
            
    return {"unicos": unicos, "omitidos": omitidos}


def detectar_conflictos(registros_normalizados: list[dict], clave: str = "id_transaccion") -> dict:
    """Agrupa por clave de negocio. Si un grupo tiene contenido distinto,
    todas las versiones conflictivas van a rechazados.
    """
    grupos: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for pos, r in enumerate(registros_normalizados, start=1):
        valor = r.get(clave)
        if valor is None or valor == "":
            grupos[f"__sin_clave__{pos}"].append((pos, r))
        else:
            grupos[str(valor)].append((pos, r))

    candidatos: list[dict] = []
    rechazados: list[dict] = []
    
    for clave_val, miembros in grupos.items():
        if len(miembros) == 1:
            candidatos.append(miembros[0][1])
            continue
            
        contenidos = {json.dumps(r, sort_keys=True, default=str) for _, r in miembros}
        
        if len(contenidos) == 1:
            # Todos idénticos: conservar el primero, el resto a rechazados
            candidatos.append(miembros[0][1])
            for pos, r in miembros[1:]:
                rechazados.append({
                    "posicion": pos,
                    "referencia_conservada": miembros[0][0],
                    "motivo": "DUPLICADO_NORMALIZADO",
                    "original_json": r,
                })
        else:
            # Contenido distinto: mandar todas las versiones a cuarentena
            for pos, r in miembros:
                rechazados.append({
                    "posicion": pos,
                    "motivo": "CLAVE_CONFLICTIVA",
                    "detalle": f"Clave {clave_val} tiene contenido distinto",
                    "original_json": r,
                })
                
    return {"candidatos": candidatos, "rechazados": rechazados}