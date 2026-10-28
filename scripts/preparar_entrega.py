"""Genera una entrega nueva; no modifica la base interactiva ni sobreescribe entregas."""
import argparse
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path
from collections import Counter
from src.pipeline import ejecutar_lote
from src.persistence import _json_dumps


def main():
    p=argparse.ArgumentParser();p.add_argument('--salida',default='entrega');p.add_argument('--evidencia');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(a.salida);out.mkdir(parents=True,exist_ok=True)
    evidence_dir=Path(a.evidencia) if a.evidencia else (root/'docs/evidencia' if out.resolve()==root/'entrega' else out.parent/(out.name+'_evidencia'))
    evidence_dir.mkdir(parents=True,exist_ok=True)
    db=out/'pipeline_banco.sqlite'
    if db.exists():raise SystemExit('La base de entrega ya existe. Selecciona otra carpeta con --salida.')
    results=[ejecutar_lote(root/'datasets/transacciones_atm.xlsx','ATM',root/'datasets/catalogo_cuentas.csv',db),ejecutar_lote(root/'datasets/transferencias_digitales.json','DIGITAL',None,db)]
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    evidence={r['ejecucion_id']:json.loads(r['datos']) for r in c.execute('SELECT * FROM evidencia_lotes')}
    clean=[json.loads(r[0]) for r in c.execute('SELECT payload FROM transacciones_limpias')]
    reasons=Counter(k for r in c.execute('SELECT motivo_rechazo_cuarentena FROM cuarentena_errores') for k in set(r[0].split('; ')))
    missing={}
    for source in ('ATM','DIGITAL'):
        meta=next(v for v in evidence.values() if v['fuente']==source)
        missing[source]=meta['perfil_inicial']['metricas_por_campo']
    summary=dict(resultados=results,integridad='ok',motivos=dict(reasons),outliers=sum(bool(r['es_outlier']) for r in clean),imputados=sum(bool(r.get('_cambios_imputacion')) for r in clean),segmentos=dict(Counter(r['segmento'] for r in clean)),faltantes=missing,evidencia=evidence,commit_codigo=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    summary['arbol_modificado']=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
    summary['version_reglas']='1.5'
    summary['version_proceso']='2.1'
    c.close()
    (evidence_dir/'resultados.json').write_text(_json_dumps(summary),encoding='utf-8')
    sources=[root/'datasets'/n for n in ('catalogo_cuentas.csv','transacciones_atm.xlsx','transferencias_digitales.json')]
    manifest={str(f.relative_to(root) if f.is_absolute() and f.is_relative_to(root) else f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [*sources,db,evidence_dir/'resultados.json']}
    (evidence_dir/'SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('evidencia','faltantes')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
