"""Orquestación: archivos y formularios recorren el mismo proceso auditable."""
import hashlib
import json
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from threading import RLock
from src.calidad import perfilar, comparar_calidad
from src.catalogo import activar_catalogo, obtener_catalogo
from src.duplicados import separar_exactos
from src.integracion import normalizar, cruzar_catalogo, rechazo, money
from src.lectura import leer_fuente
from src.limpieza import imputar, aplicar_iqr
from src.persistence import initialize_database, persist_batch, build_load_identity, _json_dumps
from src.transformacion import escalar_segmentar

RULES='1.4'; PROCESS='2.0'; LOCK=RLock()


def _error(item):
    return rechazo(item['original_json'],item['motivo'],item.get('campo',''),fase='TRANSFORMACION')


def _run(rows,source,db,metadata,identity,reference=None):
    version,catalog=obtener_catalogo(db)
    metadata.update(catalog_version=version,rules_version=RULES,process_version=PROCESS)
    before=perfilar([r if isinstance(r,dict) else {'_valor':r} for r in rows],source)
    # Duplicación exacta antes de incorporar posiciones, reutilizando el módulo de Maki.
    dedup=separar_exactos(rows); omitted_positions={r['posicion'] for r in dedup['omitidos']}
    candidates=[];omitted=[];bad=[]
    for i,raw in enumerate(rows,1):
        r={**(raw if isinstance(raw,dict) else {}),'original_json':raw,'fila_origen':i+metadata.get('offset',1)-1,
           'archivo_origen':metadata['archivo'],'origen_ingreso':metadata.get('origen','ARCHIVO')}
        if i in omitted_positions: omitted.append({'record':r,'resultado':'DUPLICADO_INTERNO'})
        else:candidates.append(r)
    parsed=normalizar(candidates,source);bad.extend(parsed['rechazados'])
    groups=defaultdict(list)
    for r in parsed['candidatos']:groups[r['id_transaccion']].append(r)
    unique=[]
    for key,rs in groups.items():
        if len({r['huella_origen'] for r in rs})>1:
            bad.extend(rechazo(r,'ID_DUPLICADO_CONFLICTIVO') for r in rs)
        else:
            unique.append(rs[0]);omitted.extend({'record':r,'resultado':'DUPLICADO_INTERNO'} for r in rs[1:])
    conn=initialize_database(db)
    new=[]
    try:
        for r in unique:
            existing=conn.execute('SELECT id,huella_origen FROM transacciones_limpias WHERE fuente=? AND id_transaccion=?',(source,r['id_transaccion'])).fetchone()
            if not existing:new.append(r)
            elif existing['huella_origen']==r['huella_origen']: omitted.append({'record':r,'resultado':'YA_CARGADA','existing_id':existing['id']})
            else:bad.append(rechazo(r,'ID_DUPLICADO_CONFLICTIVO'))
    finally:conn.close()
    joined=cruzar_catalogo(new,catalog);bad.extend(joined['rechazados']);eligible=joined['candidatos']
    if metadata.get('origen')=='MANUAL':
        if reference is None:
            pending=[r for r in eligible if r['tipo_operacion']!='CONSULTA_SALDO']
            bad.extend(rechazo(r,'REFERENCIA_ESTADISTICA_INSUFICIENTE') for r in pending)
            eligible=[r for r in eligible if r['tipo_operacion']=='CONSULTA_SALDO'];reference={}
    filled=imputar(eligible,reference.get('imputacion',{}) if reference is not None else None)
    bad.extend(_error(r) for r in filled['rechazados'])
    for r in filled['candidatos']:
        r['monto_mxn']=money(r['monto_mxn']);r['version_catalogo']=version
        r['transformaciones'].extend(r.get('_cambios_imputacion',[]))
        if source=='ATM':r['comision_aplicada']=money(r['comision_aplicada'])
    capped=aplicar_iqr(filled['candidatos'],reference.get('iqr',{}) if reference is not None else None)
    scaled=escalar_segmentar(capped['candidatos'],reference.get('escala',{}) if reference is not None else None)
    bad.extend(_error(r) for r in scaled['rechazados'])
    for r in scaled['candidatos']:
        r['monto_analitico_mxn']=money(r['monto_analitico_mxn'])
        r['referencia_ejecucion']=metadata.get('referencia_ejecucion')
    metadata['parametros']={'imputacion':filled['parametros'],'iqr':capped['parametros'],'escala':scaled['parametros']}
    metadata['perfil_inicial']=before
    # Comparación sobre campos originales de cada fuente; derivados no inflan faltantes.
    final_rows=[]
    for r in scaled['candidatos']:
        rr=dict(r['registro_origen'])
        if source=='ATM': rr.update(monto_mxn=r['monto_mxn'],id_cajero=r['id_cajero'],comision_aplicada=r['comision_aplicada'])
        else:rr.update(concept=r['concept'],amount=r['monto_mxn']/r['tasa_conversion'])
        final_rows.append(rr)
    after=perfilar(final_rows,source)
    metadata['perfil_final']=after
    metadata['comparacion']=comparar_calidad(before,after,dict(imputados=sum(bool(r.get('_cambios_imputacion')) for r in scaled['candidatos']),rechazados=len(bad),duplicados_omitidos=len(omitted)))
    metadata['omitidos']=omitted
    assert len(rows)==len(scaled['candidatos'])+len(bad)+len(omitted)
    result=persist_batch(db,source,scaled['candidatos'],bad,identity_hash=identity,metadata=metadata)
    result['resultado']='EN_CUARENTENA' if result['quarantine'] else 'INSERTADA' if result['inserted'] else 'YA_CARGADA'
    return result


def ejecutar_lote(ruta,fuente,ruta_catalogo=None,ruta_bd='outputs/pipeline.sqlite'):
    with LOCK:
        content=leer_fuente(ruta,fuente)
        if ruta_catalogo:activar_catalogo(ruta_catalogo,ruta_bd)
        version,_=obtener_catalogo(ruta_bd)
        identity=build_load_identity(fuente,{'archivo':content['metadatos']['hash']},version,RULES,PROCESS)
        return _run(content['registros'],fuente,ruta_bd,{**content['metadatos'],'file_hashes':{'archivo':content['metadatos']['hash']}},identity)


def ejecutar_manual(solicitud,ruta_bd='outputs/pipeline.sqlite',reprocesar_ids=None):
    with LOCK:
        source=solicitud['fuente'];request_id=solicitud['solicitud_id']
        if source not in ('ATM','DIGITAL') or not isinstance(request_id,str) or not request_id.strip():raise ValueError('Fuente o solicitud inválida')
        digest=hashlib.sha256(_json_dumps(solicitud).encode()).hexdigest()
        identity='manual:'+request_id
        conn=initialize_database(ruta_bd);reference=None
        try:
            prior=conn.execute('SELECT e.datos FROM evidencia_lotes e JOIN ejecuciones x ON x.id=e.ejecucion_id WHERE x.identidad_carga=? AND x.estado="COMPLETADA"',(identity,)).fetchone()
            if prior and json.loads(prior[0]).get('solicitud_hash')!=digest: raise ValueError('La solicitud ya existe con otros datos; usa una solicitud nueva')
            ref=solicitud.get('referencia_ejecucion')
            if ref:
                row=conn.execute('SELECT e.datos FROM evidencia_lotes e JOIN ejecuciones x ON x.id=e.ejecucion_id WHERE x.id=? AND x.fuente=? AND x.estado="COMPLETADA" AND x.version_reglas=?',(ref,source,RULES)).fetchone()
                if row:
                    info=json.loads(row[0])
                    if info.get('origen','ARCHIVO')=='ARCHIVO':reference=info.get('parametros')
        finally:conn.close()
        return _run([solicitud['datos_origen']],source,ruta_bd,dict(archivo='FORMULARIO',origen='MANUAL',offset=1,solicitud_hash=digest,referencia_ejecucion=solicitud.get('referencia_ejecucion'),reprocesar_ids=reprocesar_ids or []),identity,reference)


def reprocesar(rejection_id,db,referencia=None,correccion=None):
    with LOCK:
        conn=initialize_database(db)
        try:row=conn.execute('SELECT * FROM cuarentena_errores WHERE id=?',(rejection_id,)).fetchone()
        finally:conn.close()
        if not row:raise ValueError('Rechazo no encontrado')
        if row['estado_seguimiento']=='RESUELTA':raise ValueError('Este rechazo ya está resuelto')
        saved=json.loads(row['original_record']);raw=correccion if correccion is not None else saved.get('original_json',saved)
        if saved.get('origen_ingreso')=='MANUAL':
            return ejecutar_manual(dict(solicitud_id=str(uuid.uuid4()),fuente=row['fuente'],datos_origen=raw,referencia_ejecucion=referencia),db,[rejection_id])
        return _run([raw],row['fuente'],db,dict(archivo='REPROCESO',offset=1,reprocesar_ids=[rejection_id]),'reproceso:'+str(uuid.uuid4()))
