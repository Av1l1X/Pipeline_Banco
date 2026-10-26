from decimal import Decimal
from src.transformacion import escalar_segmentar
from src.limpieza import imputar, aplicar_iqr


def record(n):
    return dict(fuente='ATM',tipo_operacion='RETIRO',estado_operacion='EXITOSA',id_cajero='A',comision_aplicada=Decimal('0'),monto_mxn=Decimal(str(n)),monto_analitico_mxn=Decimal(str(n)))


def test_constant_and_reference():
    result=escalar_segmentar([record(10)])
    assert result['candidatos'][0]['monto_normalizado']==0
    assert escalar_segmentar([record(20)], result['parametros'])['rechazados']


def test_decimal_imputation_and_reference():
    rows=[record(n) for n in [100,200,300,400,90000]]
    r=record(1);r['monto_mxn']=None
    result=imputar(rows+[r])
    assert result['candidatos'][-1]['monto_mxn']==Decimal(300)
    assert imputar([r],result['parametros'])['candidatos'][0]['monto_mxn']==Decimal(300)


def test_iqr_decimal_does_not_change_original():
    rows=[record(n) for n in [100,110,120,130,140,100000]]
    result=aplicar_iqr(rows)
    assert result['candidatos'][-1]['monto_mxn']==100000
    assert result['candidatos'][-1]['monto_analitico_mxn']<100000
    assert aplicar_iqr([record(200000)],result['parametros'])['candidatos'][0]['es_outlier']


def test_scaling_empty_and_bounds():
    assert not escalar_segmentar([])['candidatos']
    result=escalar_segmentar([record(1),record(2),record(3)])
    assert [r['segmento'] for r in result['candidatos']]==['BAJO','MEDIO','ALTO']
