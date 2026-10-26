"""Consultas de control: filtros comunes y conteos independientes de paginación."""
import json
from collections import Counter
from src.persistence import initialize_database


def matches(r,f):
    for key in ('fuente','tipo_operacion','estado_operacion','origen_ingreso','ejecucion_id'):
        if f.get(key) and str(r.get(key,''))!=f[key]:return False
    if f.get('q') and f['q'].lower() not in (str(r.get('id_transaccion',''))+' '+str(r.get('id_cuenta',''))).lower():return False
    date=str(r.get('fecha_procesado' if f.get('tipo_fecha')=='procesamiento' else 'fecha_hora',''))[:10]
    if f.get('desde') and date<f['desde']:return False
    if f.get('hasta') and date>f['hasta']:return False
    return True


def snapshot(db,filters=None):
    f=filters or {};c=initialize_database(db)
    try:
        clean=[]
        for row in c.execute('SELECT * FROM transacciones_limpias'):
            r={**json.loads(row['payload']),**{k:row[k] for k in ('id','ejecucion_id','fecha_procesado')}}
            if matches(r,f):clean.append(r)
        quarantine=[]
        for row in c.execute('SELECT * FROM cuarentena_errores'):
            r=dict(row);original=json.loads(r['original_record']);origin=original.get('original_json',original)
            if not isinstance(origin,dict):origin={}
            r.update(id_cuenta=original.get('id_cuenta',origin.get('account_id','')),tipo_operacion=original.get('tipo_operacion','TRANSFERENCIA' if r['fuente']=='DIGITAL' else ''),estado_operacion=original.get('estado_operacion',origin.get('resultado',origin.get('status',''))),origen_ingreso=original.get('origen_ingreso','ARCHIVO'),fecha_hora=original.get('fecha_hora',origin.get('timestamp','')))
            r['original']=original;r['errores']=json.loads(r['detalles_errores'])
            if matches(r,f):quarantine.append(r)
        executions=[]
        for row in c.execute('SELECT x.*,e.datos FROM ejecuciones x LEFT JOIN evidencia_lotes e ON x.id=e.ejecucion_id ORDER BY x.iniciada_en DESC,x.rowid DESC'):
            r=dict(row);meta=json.loads(r.pop('datos') or '{}');r['archivo']=meta.get('archivo','');r['origen_ingreso']=meta.get('origen','ARCHIVO');r['evidencia']=meta
            # Historial solo admite filtros propios de ejecución.
            if f.get('fuente') and r['fuente']!=f['fuente']:continue
            if f.get('ejecucion_id') and r['id']!=f['ejecucion_id']:continue
            if f.get('origen_ingreso') and r['origen_ingreso']!=f['origen_ingreso']:continue
            if f.get('tipo_fecha')=='procesamiento':
                if f.get('desde') and r['iniciada_en'][:10]<f['desde']:continue
                if f.get('hasta') and r['iniciada_en'][:10]>f['hasta']:continue
            executions.append(r)
        omitted=[]
        for row in c.execute('SELECT * FROM filas_omitidas'):
            r=dict(row);raw=json.loads(r['registro_origen']);r.update(tipo_operacion=raw.get('tipo_operacion','TRANSFERENCIA' if r['fuente']=='DIGITAL' else ''),estado_operacion=raw.get('resultado',raw.get('status','')),id_cuenta=raw.get('id_cuenta',raw.get('account_id','')),fecha_hora=raw.get('fecha_hora',raw.get('timestamp','')))
            parent=c.execute('SELECT datos FROM evidencia_lotes WHERE ejecucion_id=?',(r['ejecucion_id'],)).fetchone()
            r['origen_ingreso']=json.loads(parent[0]).get('origen','ARCHIVO') if parent else 'ARCHIVO'
            if matches(r,f):omitted.append(r)
        reasons=Counter(code for r in quarantine for code in set(r['motivo_rechazo_cuarentena'].split('; ')))
        return dict(limpias=clean,cuarentena=quarantine,ejecuciones=executions,omitidos=omitted,
                    resumen=dict(limpias=len(clean),cuarentena_abierta=sum(r['estado_seguimiento']=='ABIERTA' for r in quarantine),rechazos_historicos=len(quarantine),duplicados=len(omitted),lotes=sum(r['estado']=='COMPLETADA' for r in executions)),motivos=dict(reasons))
    finally:c.close()
