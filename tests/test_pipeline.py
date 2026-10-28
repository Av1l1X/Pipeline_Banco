from pathlib import Path
from src.pipeline import ejecutar_lote, reprocesar
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


def test_corrupt_element_and_reprocess(tmp_path):
    db=tmp_path/'test.sqlite';activar_catalogo(ROOT/'datasets/catalogo_cuentas.csv',db)
    p=tmp_path/'bad.json';p.write_text('[42]')
    assert ejecutar_lote(p,'DIGITAL',None,db)['quarantine']==1
    c=initialize_database(db);rid=c.execute('SELECT id FROM cuarentena_errores').fetchone()[0];c.close()
    assert reprocesar(rid,db)['quarantine']==1
