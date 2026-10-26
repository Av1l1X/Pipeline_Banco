import json
from pathlib import Path
import pytest
from src.pipeline import ejecutar_lote, ejecutar_manual, reprocesar
from src.catalogo import activar_catalogo
from src.persistence import initialize_database

ROOT=Path(__file__).resolve().parents[1]


def test_official_lots_and_repetition(tmp_path):
    db=tmp_path/'test.sqlite'
    a=ejecutar_lote(ROOT/'datasets/transacciones_atm.xlsx','ATM',ROOT/'datasets/catalogo_cuentas.csv',db)
    b=ejecutar_lote(ROOT/'datasets/transferencias_digitales.json','DIGITAL',None,db)
    assert a['read']==620 and a['internal_duplicates']==20 and b['read']==600
    for x in (a,b): assert x['read']==sum(x[k] for k in ('inserted','quarantine','internal_duplicates','already_loaded'))
    again=ejecutar_lote(ROOT/'datasets/transacciones_atm.xlsx','ATM',None,db)
    assert again['already_processed']
    c=initialize_database(db)
    assert c.execute('SELECT count(*) FROM transacciones_limpias').fetchone()[0]==a['inserted']+b['inserted']
    c.close()


def test_manual_request_identity_and_missing_reference(tmp_path):
    db=tmp_path/'test.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    raw=dict(id_transaccion='manual-1',id_cuenta='CTA-0001',fecha_hora='2026-10-25T09:00:00-06:00',tipo_operacion='CONSULTA_SALDO',monto_mxn=0,id_cajero='A',resultado='EXITOSA',comision_aplicada=0)
    request=dict(solicitud_id='r1',fuente='ATM',datos_origen=raw)
    assert ejecutar_manual(request,db)['inserted']==1
    assert ejecutar_manual(request,db)['already_processed']
    with pytest.raises(ValueError):ejecutar_manual({**request,'datos_origen':{**raw,'id_cajero':'B'}},db)
    raw.update(id_transaccion='manual-2',tipo_operacion='RETIRO',monto_mxn=100)
    assert ejecutar_manual({**request,'solicitud_id':'r2'},db)['quarantine']==1


def test_corrupt_element_and_reprocess(tmp_path):
    db=tmp_path/'test.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    p=tmp_path/'bad.json';p.write_text('[42]')
    assert ejecutar_lote(p,'DIGITAL',None,db)['quarantine']==1
    c=initialize_database(db);rid=c.execute('SELECT id FROM cuarentena_errores').fetchone()[0];c.close()
    assert reprocesar(rid,db)['quarantine']==1
