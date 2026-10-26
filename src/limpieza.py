"""M3/M4 de Maki: adaptación para Decimal y referencias guardadas."""
from decimal import Decimal
from statistics import median
from src.transformacion import percentil
MIN_OBSERVACIONES = 5

def _es_nulo_o_vacio(v):
    return v is None or isinstance(v,str) and not v.strip()

def _es_numero_valido(v, zero=False):
    return isinstance(v,(int,float,Decimal)) and not isinstance(v,bool) and Decimal(str(v)).is_finite() and (v >= 0 if zero else v > 0)

def _key(r, field):
    group = (r.get('tipo_operacion'),r.get('id_cajero')) if field=='comision_aplicada' else ((r.get('tipo_operacion'),r.get('estado_operacion')) if r.get('fuente')=='ATM' else (r.get('moneda_original'),r.get('estado_operacion')))
    return '|'.join(str(x or '') for x in (r.get('fuente'),field,*group))

def imputar(registros,parametros=None):
    params={} if parametros is None else parametros
    if parametros is None:
        groups={}
        for r in registros:
            for field in ('monto_mxn','comision_aplicada'):
                if field=='comision_aplicada' and (r.get('fuente')!='ATM' or not r.get('id_cajero') or r.get('id_cajero')=='DESCONOCIDO'): continue
                if r.get('tipo_operacion')=='CONSULTA_SALDO' and field=='monto_mxn': continue
                value=r.get(field)
                if _es_numero_valido(value,field=='comision_aplicada') and not r.get('_cambios_imputacion'):
                    groups.setdefault(_key(r,field),[]).append(Decimal(str(value)))
        for key,values in groups.items():
            params[key]=dict(mediana=median(values),tamano_grupo=len(values),media=sum(values)/len(values))
    candidates,rejected=[],[]
    for raw in registros:
        r=dict(raw);changes=[];errors=[]
        for field in (('id_cajero',) if r.get('fuente')=='ATM' else ('concept',)):
            if _es_nulo_o_vacio(r.get(field)):
                r[field]='DESCONOCIDO' if field=='id_cajero' else 'SIN_CONCEPTO'
                changes.append(dict(campo=field,antes=raw.get(field),despues=r[field],regla='DETERMINISTA'))
        for field in ('monto_mxn','comision_aplicada'):
            if field=='comision_aplicada' and (r.get('fuente')!='ATM' or field not in r): continue
            value=r.get(field)
            if _es_nulo_o_vacio(value):
                if field=='monto_mxn' and r.get('tipo_operacion')=='CONSULTA_SALDO':
                    r[field]=Decimal(0);rule='CONSULTA_SALDO_CERO'
                else:
                    info=params.get(_key(r,field),{})
                    if info.get('tamano_grupo',0)<5:
                        errors.append(field);continue
                    r[field]=Decimal(str(info['mediana']));rule='MEDIANA_GRUPO'
                changes.append(dict(campo=field,antes=value,despues=r[field],regla=rule,grupo=_key(r,field)))
            elif not _es_numero_valido(value,field=='comision_aplicada' or r.get('tipo_operacion')=='CONSULTA_SALDO'):
                rejected.append(dict(original_json=raw,motivo='FORMATO_NUMERICO_INVALIDO',campo=field));break
        else:
            if errors:
                rejected.append(dict(original_json=raw,motivo='SIN_BASE_PARA_IMPUTAR',campo=','.join(errors)));continue
            r['_cambios_imputacion']=changes;candidates.append(r)
    return dict(candidatos=candidates,rechazados=rejected,parametros=params)

def aplicar_iqr(registros,parametros=None):
    params={} if parametros is None else parametros
    if parametros is None:
        groups={}
        for r in registros:
            key=r.get('fuente','')+'|'+r.get('tipo_operacion','');groups.setdefault(key,[])
            imputed=any(c['campo']=='monto_mxn' and c['regla']=='MEDIANA_GRUPO' for c in r.get('_cambios_imputacion',[]))
            if r.get('tipo_operacion')!='CONSULTA_SALDO' and not imputed and _es_numero_valido(r.get('monto_mxn')): groups[key].append(r['monto_mxn'])
        for key,values in groups.items():
            if len(values)<5:
                params[key]=dict(recorte=False,motivo='GRUPO_MENOR_A_5',n=len(values));continue
            a,b=percentil(values,'.25'),percentil(values,'.75');iqr=b-a
            params[key]=dict(recorte=iqr>0,motivo='IQR' if iqr else 'IQR_CERO',n=len(values),q1=a,q3=b,iqr=iqr,limite_inferior=max(Decimal(0),a-Decimal('1.5')*iqr),limite_superior=b+Decimal('1.5')*iqr)
    candidates=[]
    for raw in registros:
        r=dict(raw);value=Decimal(str(r['monto_mxn']));info=params.get(r.get('fuente','')+'|'+r.get('tipo_operacion',''),{})
        r['monto_analitico_mxn']=value;r['es_outlier']=False
        if info.get('recorte') and r.get('tipo_operacion')!='CONSULTA_SALDO':
            lo,hi=Decimal(str(info['limite_inferior'])),Decimal(str(info['limite_superior']))
            r['monto_analitico_mxn']=min(hi,max(lo,value));r['es_outlier']=value!=r['monto_analitico_mxn']
        r['parametros_iqr']=info;candidates.append(r)
    return dict(candidatos=candidates,parametros=params)
