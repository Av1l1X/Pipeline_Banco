from pathlib import Path
from fastapi.testclient import TestClient
from src.api import create_app
from src.catalogo import activar_catalogo
from tests.test_pipeline import ROOT


def upload(client, source, name, data, endpoint='/api/cargas'):
    return client.post(endpoint, data={'fuente': source}, files={'archivo': (name, data)})


def test_api_upload_and_filters(tmp_path):
    db=tmp_path/'a.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    client=TestClient(create_app(db))
    r=upload(client,'DIGITAL','mi_lote_octubre.json',(ROOT/'datasets/transferencias_digitales.json').read_bytes())
    assert r.status_code==200 and r.json()['inserted']==504
    control=client.get('/api/control?fuente=DIGITAL').json()
    assert control['resumen']['limpias']==504
    assert client.get('/api/control?fuente=ATM').json()['resumen']['limpias']==0


def test_bad_upload_and_origin(tmp_path):
    client=TestClient(create_app(tmp_path/'a.sqlite'))
    assert upload(client,'DIGITAL','bad.json',b'{}').status_code==422
    assert client.post('/api/sesiones',headers={'Origin':'https://example.com'},json={}).status_code==403
    assert client.post('/api/transacciones',json={}).status_code==404


def test_selected_files_evidence_and_session_isolation(tmp_path):
    app=create_app(tmp_path/'previous.sqlite',demo_root=tmp_path/'sesiones');client=TestClient(app)
    assert client.post('/api/sesiones',json={}).status_code==200
    first_db=app.state.db
    assert client.get('/api/estado').json()['catalogo'] is None
    assert client.get('/api/control').json()['resumen']['limpias']==0
    for source,original,name in [('CATALOGO','catalogo_cuentas.csv','cuentas.csv'),('ATM','transacciones_atm.xlsx','operaciones_nuevas.xlsx'),('DIGITAL','transferencias_digitales.json','transferencias_octubre.json')]:
        response=upload(client,source,name,(ROOT/'datasets'/original).read_bytes())
        assert response.status_code==200
    state=client.get('/api/control').json()
    assert state['resumen']['limpias']==1072
    assert state['resumen']['rechazos_historicos']==128
    assert state['resumen']['duplicados']==20
    assert sum(x['filas_leidas'] for x in state['ejecuciones'])==1220
    for run in state['ejecuciones']:
        assert len(run['evidencia']['etapas'])==7
        assert run['evidencia']['etapas'][-1]['cantidad']==run['nuevas_limpias']
    repeated=upload(client,'DIGITAL','otro_nombre.json',(ROOT/'datasets/transferencias_digitales.json').read_bytes())
    assert repeated.json()['already_processed']
    client.post('/api/sesiones',json={})
    assert app.state.db!=first_db and Path(first_db).exists()
    assert client.get('/api/control').json()['resumen']['limpias']==0
    assert client.get('/api/estado').json()['catalogo'] is None
    for removed in ['/atm','/digital','/api/demo/entrada','/presentacion']:
        assert client.get(removed).status_code==404


def test_preview_does_not_ingest_and_rejects_bad_files(tmp_path):
    client=TestClient(create_app(tmp_path/'a.sqlite'))
    data=(ROOT/'datasets/transferencias_digitales.json').read_bytes()
    response=upload(client,'DIGITAL','../nuevo.json',data,'/api/archivos/vista-previa')
    assert response.status_code==200
    assert response.json()['archivo']=='nuevo.json'
    assert response.json()['filas']==600 and len(response.json()['muestra'])==5
    assert client.get('/api/control').json()['resumen']['lotes']==0
    assert not list((tmp_path/'uploads').glob('*'))
    for source,name,data in [('ATM','x.csv',b'wrong,headers\n1,2'),('DIGITAL','x.json',b'[]'),('DIGITAL','x.json',b'{}'),('DIGITAL','x.txt',b'[]'),('CATALOGO','x.csv',b'')]:
        assert upload(client,source,name,data,'/api/archivos/vista-previa').status_code==422
    assert client.get('/api/control').json()['resumen']['limpias']==0
