from fastapi.testclient import TestClient
from src.api import create_app


def test_unreadable_uploads_are_controlled(tmp_path):
    c=TestClient(create_app(tmp_path/'upload.sqlite'))
    for source,name,data in [('ATM','broken.xlsx',b'not a workbook'),('DIGITAL','bad.json',b'[NaN]'),('DIGITAL','bad.json',b'not json')]:
        assert c.post('/api/cargas',data={'fuente':source},files={'archivo':(name,data)}).status_code==422
