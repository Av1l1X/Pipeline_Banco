from src.calidad import perfilar
from src.duplicados import separar_exactos, detectar_conflictos
import json


def test_perfilar_no_muta_entrada():
    registros = [
        {"id": "1", "monto": 100, "correo": None},
        {"id": "2", "monto": None, "correo": ""},
        {"id": "1", "monto": 100, "correo": None},  # duplicado exacto
    ]
    original = json.dumps(registros, sort_keys=True)
    p = perfilar(registros, "ATM")
    assert json.dumps(registros, sort_keys=True) == original
    assert p["filas"] == 3
    assert p["duplicados_exactos"] == 1
    assert p["metricas_por_campo"]["correo"]["nulos"] == 2
    assert p["metricas_por_campo"]["correo"]["vacios"] == 1
    assert p["metricas_por_campo"]["monto"]["nulos"] == 1


def test_separar_exactos_conserva_primera():
    regs = [{"a": 1}, {"a": 1}, {"a": 2}, {"a": 1}]
    r = separar_exactos(regs)
    assert len(r["unicos"]) == 2
    assert len(r["omitidos"]) == 2
    assert r["omitidos"][0]["referencia_conservada"] == 1
    assert r["omitidos"][1]["referencia_conservada"] == 1


def test_detectar_conflictos_misma_clave_distinto_contenido():
    regs = [
        {"id_transaccion": "T1", "monto": 100},
        {"id_transaccion": "T1", "monto": 200},  # conflicto
        {"id_transaccion": "T2", "monto": 50},   # ok
    ]
    r = detectar_conflictos(regs)
    assert len(r["candidatos"]) == 1
    assert r["candidatos"][0]["id_transaccion"] == "T2"
    assert len(r["rechazados"]) == 2
    assert all(x["motivo"] == "CLAVE_CONFLICTIVA" for x in r["rechazados"])


def test_detectar_conflictos_misma_clave_identico_contenido():
    regs = [
        {"id_transaccion": "T1", "monto": 100},
        {"id_transaccion": "T1", "monto": 100},
    ]
    r = detectar_conflictos(regs)
    assert len(r["candidatos"]) == 1
    assert len(r["rechazados"]) == 1
    assert r["rechazados"][0]["motivo"] == "DUPLICADO_NORMALIZADO"