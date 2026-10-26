import json
from src.pipeline import ejecutar_lote, ejecutar_manual
from src.catalogo import activar_catalogo
from src.persistence import initialize_database
from fastapi.testclient import TestClient
from src.api import create_app
from tests.test_pipeline import ROOT


def test_manual_reference_and_duplicate_confirmation(tmp_path):
    db=tmp_path/'manual.sqlite'
    ref=ejecutar_lote(ROOT/'datasets/transacciones_atm.xlsx','ATM',ROOT/'datasets/catalogo_cuentas.csv',db)
    raw=dict(id_transaccion='UI-TEST',id_cuenta='CTA-0001',fecha_hora='2026-10-25T09:00:00-06:00',tipo_operacion='RETIRO',monto_mxn='20.50',id_cajero='ATM-COL-01',resultado='EXITOSA',comision_aplicada='0')
    request=dict(solicitud_id='ui-test',fuente='ATM',datos_origen=raw,referencia_ejecucion=ref['execution_id'])
    first=ejecutar_manual(request,db)
    assert first['inserted']==1 and first['motivos']==[]
    assert ejecutar_manual(request,db)['already_processed']
    c=initialize_database(db)
    row=json.loads(c.execute("SELECT payload FROM transacciones_limpias WHERE id_transaccion='UI-TEST'").fetchone()[0]);c.close()
    assert row['monto_mxn']=='20.50' and row['referencia_ejecucion']==ref['execution_id']
    assert 0<=row['monto_normalizado']<=1


def test_quarantine_receipt_is_stable(tmp_path):
    db=tmp_path/'bad.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    c=TestClient(create_app(db))
    body=dict(solicitud_id='invalid',fuente='DIGITAL',datos_origen=dict(transfer_id='BAD',timestamp='2026-10-25T09:00:00-06:00',account_id='CTA-0001',amount=100,currency='MXN',beneficiary_clabe='123',notification_email=None,concept='Prueba',status='LIQUIDADA',platform='Web Banking'))
    r=c.post('/api/transacciones',json=body).json()
    assert r['resultado']=='EN_CUARENTENA' and 'CLABE_INVALIDA' in r['motivos']
    again=c.post('/api/transacciones',json=body).json()
    assert again['already_processed'] and again['motivos']==r['motivos']


def test_unreadable_uploads_are_controlled(tmp_path):
    c=TestClient(create_app(tmp_path/'upload.sqlite'))
    for source,name,data in [('ATM','broken.xlsx',b'not a workbook'),('DIGITAL','bad.json',b'[NaN]'),('DIGITAL','bad.json',b'not json')]:
        assert c.post('/api/cargas',data={'fuente':source},files={'archivo':(name,data)}).status_code==422
