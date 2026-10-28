from pathlib import Path
import json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[2]
def main():
 role=sys.argv[1].lower() if len(sys.argv)>1 else ''
 if role not in {'maki','avilix','leo'}:
  raise SystemExit('Uso: python docs/guias/consultar_ejemplos.py maki|avilix|leo')
 with sqlite3.connect((ROOT/'entrega/pipeline_banco.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row
  def registro(ident):
   row=db.execute('SELECT payload FROM transacciones_limpias WHERE id_transaccion=?',(ident,)).fetchone()
   return json.loads(row['payload'])
  atm=registro('ATM-TX-00034');digital=registro('SPEI-2026-00003')
  evidence=json.loads((ROOT/'docs/evidencia/resultados.json').read_text(encoding='utf-8'))
  if role=='maki':
   result={'ejemplo_imputacion':atm,'ejemplo_iqr':digital['parametros_iqr'],'evidencia_estadistica':{k:{f:v[f] for f in ('comparacion','parametros') if f in v} for k,v in evidence['evidencia'].items()}}
  elif role=='avilix':
   result={'ejemplo_divisas':digital,'ejemplo_escala':atm,'parametros':{k:v.get('parametros',{}) for k,v in evidence['evidencia'].items()}}
  else:
   reject=dict(db.execute("SELECT * FROM cuarentena_errores WHERE id_transaccion='ATM-TX-00009'").fetchone())
   result={'limpias':db.execute('SELECT COUNT(*) FROM transacciones_limpias').fetchone()[0],'cuarentena':db.execute('SELECT COUNT(*) FROM cuarentena_errores').fetchone()[0],'integridad':db.execute('PRAGMA integrity_check').fetchone()[0],'referencias_incumplidas':[list(x) for x in db.execute('PRAGMA foreign_key_check')],'ejemplo_rechazo':reject,'estado_bancario_de_registro_limpio':digital['estado_operacion']}
  print(json.dumps(result,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
