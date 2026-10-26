"""Versiones completas y activación atómica del catálogo."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from src.lectura import leer_fuente
from src.persistence import initialize_database, _json_dumps


def activar_catalogo(path, db):
    source=leer_fuente(path,'CATALOGO'); accounts={}
    for raw in source['registros']:
        r={k:v.strip() if isinstance(v,str) else v for k,v in raw.items()}
        key=r.get('id_cuenta','').upper(); r['id_cuenta']=key
        if not key or key in accounts: raise ValueError('Catálogo con cuenta vacía o duplicada')
        if not r.get('titular') or not r.get('tipo_cuenta'): raise ValueError('Titular o tipo de cuenta ausente')
        date.fromisoformat(r['fecha_apertura'])
        credit=Decimal(str(r['limite_credito_mxn']))
        if not credit.is_finite() or credit<0: raise ValueError('Límite de crédito inválido')
        r['limite_credito_mxn']=credit;r['estado_cuenta']=r['estado_cuenta'].upper()
        if r['estado_cuenta'] not in ('ACTIVA','BLOQUEADA','SUSPENDIDA'): raise ValueError('Estado de cuenta inválido')
        accounts[key]=r
    if not accounts: raise ValueError('Catálogo vacío')
    digest=hashlib.sha256(_json_dumps(accounts).encode()).hexdigest();version='cat-'+digest[:16]
    conn=initialize_database(db)
    try:
        conn.execute('BEGIN IMMEDIATE')
        old=conn.execute('SELECT version FROM catalogo_activo WHERE id=1').fetchone()
        if old:
            ids={x[0] for x in conn.execute('SELECT id_cuenta FROM catalogo_cuentas WHERE version_catalogo=?',(old[0],))}
            if not ids<=accounts.keys(): raise ValueError('El catálogo actualizado no puede eliminar cuentas anteriores')
        if not conn.execute('SELECT 1 FROM catalogo_versiones WHERE version=?',(version,)).fetchone():
            conn.execute('INSERT INTO catalogo_versiones(version,hash_contenido) VALUES (?,?)',(version,digest))
            conn.executemany('INSERT INTO catalogo_cuentas VALUES (?,?,?)',[(version,k,_json_dumps(v)) for k,v in accounts.items()])
        conn.execute('INSERT OR REPLACE INTO catalogo_activo VALUES (1,?)',(version,));conn.commit()
    except Exception:
        conn.rollback();raise
    finally: conn.close()
    return version


def obtener_catalogo(db):
    c=initialize_database(db)
    try:
        v=c.execute('SELECT version FROM catalogo_activo WHERE id=1').fetchone()
        if not v: raise ValueError('Primero carga un catálogo válido')
        return v[0],{r['id_cuenta']:json.loads(r['atributos_json']) for r in c.execute('SELECT * FROM catalogo_cuentas WHERE version_catalogo=?',(v[0],))}
    finally:c.close()
