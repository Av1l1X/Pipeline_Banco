import json
from decimal import Decimal
import pytest
from src.lectura import leer_fuente
from src.integracion import normalizar, cruzar_catalogo


def digital(**changes):
    return dict(transfer_id='x', timestamp=1788816180, account_id='a', amount='100', currency='USD', beneficiary_clabe='012345678901234567', notification_email='', concept='Renta', status='liquidada', platform='Web Banking', **changes)


def test_conversion_and_identity():
    r = normalizar([digital()], 'DIGITAL')['candidatos'][0]
    assert r['monto_mxn'] == Decimal('1950.00')
    assert r['beneficiary_clabe'].startswith('0')
    assert r['fecha_hora'].utcoffset().total_seconds() == -21600
    assert cruzar_catalogo([r], {})['rechazados'][0]['reasons'] == ['CUENTA_NO_REGISTRADA']


def test_invalid_json_root(tmp_path):
    p = tmp_path/'data.json'; p.write_text('{}')
    with pytest.raises(ValueError): leer_fuente(p, 'DIGITAL')


def test_bad_rows_survive_reading(tmp_path):
    p = tmp_path/'data.json'; p.write_text(json.dumps([digital(), 42]))
    assert len(leer_fuente(p, 'DIGITAL')['registros']) == 2
    assert normalizar([{'original_json': 42}], 'DIGITAL')['rechazados']


def test_ambiguous_atm_dates_rejected():
    r = {'id_transaccion':'a','id_cuenta':'b','fecha_hora':'12/09/2026','tipo_operacion':'RETIRO','monto_mxn':100,'resultado':'EXITOSA'}
    assert normalizar([r], 'ATM')['rechazados'][0]['reasons'] == ['FECHA_INVALIDA']
