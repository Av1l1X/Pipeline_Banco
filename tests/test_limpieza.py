from src.limpieza import imputar, aplicar_iqr

def test_consulta_saldo_cero():
    regs = [{"tipo_operacion": "CONSULTA_SALDO", "monto_mxn": None, "fuente": "ATM", "estado_operacion": "EXITOSA"}]
    r = imputar(regs)
    assert r["candidatos"][0]["monto_mxn"] == 0

def test_mediana_con_cinco_observaciones():
    base = {"tipo_operacion": "RETIRO", "estado_operacion": "EXITOSA", "fuente": "ATM"}
    regs = [dict(base, monto_mxn=m) for m in (100, 200, 300, 400, 500)]
    regs.append(dict(base, monto_mxn=None))
    r = imputar(regs)
    assert r["candidatos"][-1]["monto_mxn"] == 300  # Mediana de 100, 200, 300, 400, 500

def test_grupo_insuficiente_rechaza():
    base = {"tipo_operacion": "RETIRO", "estado_operacion": "FALLO", "fuente": "ATM"}
    regs = [dict(base, monto_mxn=m) for m in (100, 200, 300, 400)]  # 4 < 5
    regs.append(dict(base, monto_mxn=None))
    r = imputar(regs)
    assert any(x["motivo"] == "SIN_BASE_PARA_IMPUTAR" for x in r["rechazados"])

def test_iqr_recorta_sin_perder_fila():
    base = {"fuente": "ATM", "tipo_operacion": "RETIRO", "estado_operacion": "EXITOSA"}
    regs = [dict(base, monto_mxn=m) for m in (100, 110, 120, 130, 140, 100000)]
    r = aplicar_iqr(regs)
    assert len(r["candidatos"]) == 6
    # El valor de 100,000 debe ser recortado a un valor menor
    assert r["candidatos"][-1]["monto_analitico_mxn"] < 100000 
    assert r["candidatos"][-1]["es_outlier"] is True