from fastapi.testclient import TestClient
from src.api import create_app
from src.catalogo import activar_catalogo
from tests.test_pipeline import ROOT


def test_api_upload_and_filters(tmp_path):
    db=tmp_path/'a.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    client=TestClient(create_app(db))
    with open(ROOT/'datasets/transferencias_digitales.json','rb') as f:
        r=client.post('/api/cargas',data={'fuente':'DIGITAL'},files={'archivo':('datos.json',f,'application/json')})
    assert r.status_code==200 and r.json()['inserted']==504
    control=client.get('/api/control?fuente=DIGITAL').json()
    assert control['resumen']['limpias']==504
    assert client.get('/api/control?fuente=ATM').json()['resumen']['limpias']==0
    assert client.get('/api/referencias?fuente=DIGITAL').json()


def test_bad_upload_and_origin(tmp_path):
    client=TestClient(create_app(tmp_path/'a.sqlite'))
    assert client.post('/api/cargas',data={'fuente':'DIGITAL'},files={'archivo':('bad.json',b'{}')}).status_code==422
    assert client.post('/api/transacciones',headers={'Origin':'https://example.com'},json={}).status_code==403
    assert client.post('/api/transacciones',json={}).status_code==422
