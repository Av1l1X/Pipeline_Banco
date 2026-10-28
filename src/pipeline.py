"""Orquestación: archivos recorren un proceso auditable."""
import json
import uuid
from collections import defaultdict
from threading import RLock
from src.calidad import perfilar, comparar_calidad
from src.catalogo import activar_catalogo, obtener_catalogo
from src.duplicados import separar_exactos
from src.integracion import normalizar, cruzar_catalogo, rechazo, money
from src.lectura import leer_fuente
from src.limpieza import imputar, aplicar_iqr
from src.persistence import initialize_database, persist_batch, build_load_identity
from src.transformacion import escalar_segmentar

RULES='1.5'; PROCESS='2.1'; LOCK=RLock()


def _error(item):
    return rechazo(item['original_json'],item['motivo'],item.get('campo',''),fase='TRANSFORMACION')


def _run(rows,source,db,metadata,identity):
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
    filled=imputar(eligible)
    bad.extend(_error(r) for r in filled['rechazados'])
    for r in filled['candidatos']:
        r['monto_mxn']=money(r['monto_mxn']);r['version_catalogo']=version
        r['transformaciones'].extend(r.get('_cambios_imputacion',[]))
        if source=='ATM':r['comision_aplicada']=money(r['comision_aplicada'])
    capped=aplicar_iqr(filled['candidatos'])
    for r in capped['candidatos']:
        r['monto_analitico_mxn']=money(r['monto_analitico_mxn'])
    scaled=escalar_segmentar(capped['candidatos'])
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
    metadata['etapas']=[
        {'nombre':'Lectura y diagnóstico','cantidad':len(rows),'detalle':'Filas leídas; perfil de nulos, vacíos y tipos.'},
        {'nombre':'Duplicados exactos','cantidad':len(omitted_positions),'detalle':'Copias adicionales separadas antes de validar.'},
        {'nombre':'Validación y normalización','cantidad':len(parsed['candidatos']),'detalle':'Candidatos con formatos válidos; fechas y divisas estandarizadas.'},
        {'nombre':'Cruce de catálogo','cantidad':len(eligible),'detalle':'Registros nuevos con cuenta existente.'},
        {'nombre':'Imputación','cantidad':sum(bool(r.get('_cambios_imputacion')) for r in filled['candidatos']),'detalle':'Registros con cambios en esta etapa; mediana por grupo.'},
        {'nombre':'IQR y transformación','cantidad':len(scaled['candidatos']),'detalle':'Aceptadas con monto analítico, MinMax y segmento.'},
        {'nombre':'Persistencia','cantidad':len(scaled['candidatos']),'detalle':f'{len(bad)} en cuarentena y {len(omitted)} omitidas. Evidencia confirmada con el lote.'}
    ]
    metadata['omitidos']=omitted
    assert len(rows)==len(scaled['candidatos'])+len(bad)+len(omitted)
    result=persist_batch(db,source,scaled['candidatos'],bad,identity_hash=identity,metadata=metadata)
    result['resultado']='EN_CUARENTENA' if result['quarantine'] else 'INSERTADA' if result['inserted'] else 'YA_CARGADA'
    conn=initialize_database(db)
    try:
        result['motivos']=sorted({reason for row in conn.execute(
            'SELECT motivo_rechazo_cuarentena FROM cuarentena_errores WHERE ejecucion_id=?',
            (result['execution_id'],)) for reason in row[0].split('; ')})
    finally:conn.close()
    return result


def ejecutar_lote(ruta,fuente,ruta_catalogo=None,ruta_bd='outputs/pipeline.sqlite'):
    with LOCK:
        content=leer_fuente(ruta,fuente)
        if ruta_catalogo:activar_catalogo(ruta_catalogo,ruta_bd)
        version,_=obtener_catalogo(ruta_bd)
        identity=build_load_identity(fuente,{'archivo':content['metadatos']['hash']},version,RULES,PROCESS)
        return _run(content['registros'],fuente,ruta_bd,{**content['metadatos'],'file_hashes':{'archivo':content['metadatos']['hash']}},identity)


def reprocesar(rejection_id,db,correccion=None):
    with LOCK:
        conn=initialize_database(db)
        try:row=conn.execute('SELECT * FROM cuarentena_errores WHERE id=?',(rejection_id,)).fetchone()
        finally:conn.close()
        if not row:raise ValueError('Rechazo no encontrado')
        if row['estado_seguimiento']=='RESUELTA':raise ValueError('Este rechazo ya está resuelto')
        saved=json.loads(row['original_record']);raw=correccion if correccion is not None else saved.get('original_json',saved)
        return _run([raw],row['fuente'],db,dict(archivo='REPROCESO',offset=1,reprocesar_ids=[rejection_id]),'reproceso:'+str(uuid.uuid4()))
