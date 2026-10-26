import sqlite3

import pytest

from src.validation import (
    ATMTransaction,
    DigitalTransaction,
    validate_atm_record_detailed,
    validate_digital_record_detailed,
)
from src.persistence import (
    build_load_identity,
    fetch_summary,
    initialize_database,
    persist_batch,
    store_catalog_version,
)
from src.validation import validate_atm_record, validate_digital_record


def test_atm_valid_record_passes():
    raw = {
        "id_transaccion": "ATM-001",
        "fecha_hora": "2026-10-15T08:20:00",
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "RETIRO",
        "monto_mxn": 850.50,
        "id_cajero": "ATM-MZL-01",
        "resultado": "EXITOSA",
        "comision_aplicada": 15.0,
    }
    record, reasons = validate_atm_record(raw)
    assert reasons == []
    assert record is not None
    assert record.monto_mxn == 850.50


def test_atm_rejects_invalid_amount_and_missing_fields():
    raw = {
        "id_transaccion": "ATM-002",
        "fecha_hora": "2026-10-15T08:20:00",
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "CONSULTA_SALDO",
        "monto_mxn": 55,
        "id_cajero": "",
        "resultado": "EXITOSA",
        "comision_aplicada": -1,
    }
    record, reasons = validate_atm_record(raw)
    assert record is None
    assert "MONTO_INVALIDO" in reasons
    assert "COMISION_INVALIDA" in reasons


def test_digital_rejects_invalid_clabe_and_email():
    raw = {
        "transfer_id": "SPEI-001",
        "timestamp": "2026-09-12T19:49:00-06:00",
        "account_id": "CTA-0002",
        "amount": 1200.0,
        "currency": "MXN",
        "beneficiary_clabe": "0123",
        "notification_email": "correo@@sinformato",
        "concept": "Nómina",
        "status": "LIQUIDADA",
        "platform": "App Android",
    }
    record, reasons = validate_digital_record(raw)
    assert record is None
    assert "CLABE_INVALIDA" in reasons
    assert "CORREO_INVALIDO" in reasons


def test_missing_imputable_values_are_allowed_and_marked_for_pipeline():
    atm = ATMTransaction.model_validate(
        {
            "id_transaccion": " atm-010 ",
            "fecha_hora": "2026-10-15T08:20:00",
            "id_cuenta": " cta-0001 ",
            "tipo_operacion": " retiro ",
            "monto_mxn": "",
            "resultado": " exitosa ",
            "comision_aplicada": None,
        }
    )
    digital = DigitalTransaction.model_validate(
        {
            "transfer_id": " spei-010 ",
            "timestamp": "2026-09-12T19:49:00-06:00",
            "account_id": " cta-0002 ",
            "amount": None,
            "currency": " mxn ",
            "beneficiary_clabe": "012345678901234567",
            "notification_email": "   ",
            "status": " pendiente ",
            "platform": " Web Banking ",
        }
    )

    assert atm.id_transaccion == "ATM-010"
    assert atm.id_cuenta == "CTA-0001"
    assert atm.tipo_operacion == "RETIRO"
    assert atm.resultado == "EXITOSA"
    assert atm.monto_mxn is None
    assert atm.id_cajero == "DESCONOCIDO"
    assert atm.comision_aplicada is None
    assert digital.transfer_id == "SPEI-010"
    assert digital.currency == "MXN"
    assert digital.status == "PENDIENTE"
    assert digital.amount is None
    assert digital.notification_email is None
    assert digital.concept == "SIN_CONCEPTO"


def test_dates_follow_source_formats_and_normalize_to_utc_minus_six():
    atm = ATMTransaction.model_validate(
        {
            "id_transaccion": "ATM-020",
            "fecha_hora": "2026-10-15",
            "id_cuenta": "CTA-0001",
            "tipo_operacion": "CONSULTA_SALDO",
            "monto_mxn": 0,
            "resultado": "EXITOSA",
        }
    )
    digital = DigitalTransaction.model_validate(
        {
            "transfer_id": "SPEI-020",
            "timestamp": 1788816180,
            "account_id": "CTA-0001",
            "amount": 10,
            "currency": "MXN",
            "beneficiary_clabe": "012345678901234567",
            "status": "LIQUIDADA",
            "platform": "Web Banking",
        }
    )
    assert atm.fecha_hora.utcoffset().total_seconds() == -6 * 60 * 60
    assert digital.timestamp.utcoffset().total_seconds() == -6 * 60 * 60


@pytest.mark.parametrize(
    ("value", "expected_reason"),
    [
        ("12/09/2026 13:26", "FECHA_INVALIDA"),
        ("2026-02-30T10:00:00", "FECHA_INVALIDA"),
    ],
)
def test_atm_rejects_ambiguous_or_impossible_dates(value, expected_reason):
    raw = {
        "id_transaccion": "ATM-030",
        "fecha_hora": value,
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "RETIRO",
        "monto_mxn": 500,
        "resultado": "EXITOSA",
    }
    record, reasons = validate_atm_record(raw)

    assert record is None
    assert expected_reason in reasons


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity", "abc"])
def test_numeric_amounts_must_be_finite_and_convertible(amount):
    raw = {
        "id_transaccion": "ATM-040",
        "fecha_hora": "2026-10-15T08:20:00",
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "RETIRO",
        "monto_mxn": amount,
        "resultado": "EXITOSA",
    }
    record, reasons = validate_atm_record(raw)

    assert record is None
    assert "FORMATO_NUMERICO_INVALIDO" in reasons


def test_digital_clabe_accepts_only_ascii_digits():
    raw = {
        "transfer_id": "SPEI-030",
        "timestamp": "2026-09-12T19:49:00-06:00",
        "account_id": "CTA-0002",
        "amount": 1,
        "currency": "MXN",
        "beneficiary_clabe": "０１２３４５６７８９０１２３４５６７",
        "status": "LIQUIDADA",
        "platform": "Web Banking",
    }
    record, reasons = validate_digital_record(raw)

    assert record is None
    assert "CLABE_INVALIDA" in reasons


def test_unknown_categories_have_stable_quarantine_codes():
    raw = {
        "id_transaccion": "ATM-050",
        "fecha_hora": "2026-10-15T08:20:00",
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "PAGO_DESCONOCIDO",
        "monto_mxn": 100,
        "resultado": "ESTADO_DESCONOCIDO",
    }
    record, reasons = validate_atm_record(raw)

    assert record is None
    assert reasons == ["ESTADO_NO_ADMITIDO", "OPERACION_NO_ADMITIDA"]


def test_detailed_validation_returns_field_code_and_description_for_each_error():
    raw = {
        "id_transaccion": "ATM-060",
        "fecha_hora": "2026-10-15T08:20:00",
        "id_cuenta": "CTA-0001",
        "tipo_operacion": "CONSULTA_SALDO",
        "monto_mxn": 55,
        "id_cajero": "",
        "resultado": "EXITOSA",
        "comision_aplicada": -1,
    }
    record, details = validate_atm_record_detailed(raw)

    assert record is None
    assert details == [
        {
            "campo": "comision_aplicada",
            "codigo": "COMISION_INVALIDA",
            "descripcion": "La comisión no puede ser negativa.",
        },
        {
            "campo": "monto_mxn",
            "codigo": "MONTO_INVALIDO",
            "descripcion": "El monto no cumple la regla de validez para el tipo de operación.",
        },
    ]


def test_detailed_digital_validation_distinguishes_invalid_email_and_clabe():
    raw = {
        "transfer_id": "SPEI-060",
        "timestamp": "2026-09-12T19:49:00-06:00",
        "account_id": "CTA-0002",
        "amount": 100,
        "currency": "MXN",
        "beneficiary_clabe": "123",
        "notification_email": "correo@@sinformato",
        "status": "LIQUIDADA",
        "platform": "Web Banking",
    }
    record, details = validate_digital_record_detailed(raw)

    assert record is None
    assert {item["codigo"] for item in details} == {
        "CLABE_INVALIDA",
        "CORREO_INVALIDO",
    }
    assert {item["campo"] for item in details} == {
        "beneficiary_clabe",
        "notification_email",
    }


def test_persistence_inserts_clean_and_quarantine_records(tmp_path):
    db_path = tmp_path / "pipeline.sqlite"
    clean = [{
        "id_transaccion": "ATM-100",
        "fecha_hora": "2026-10-11 12:00:00",
        "id_cuenta": "CTA-0003",
        "tipo_operacion": "DEPOSITO",
        "monto_mxn": 1000,
        "id_cajero": "ATM-COL-01",
        "resultado": "EXITOSA",
        "comision_aplicada": 0,
    }]
    quarantine = [{
        "record": {
            "id_transaccion": "ATM-101",
            "monto_mxn": -5,
            "tipo_operacion": "RETIRO",
        },
        "reasons": ["MONTO_INVALIDO", "OPERACION_NO_ADMITIDA"],
        "campo_afectado": "monto_mxn",
    }]
    result = persist_batch(db_path, "ATM", clean, quarantine)
    assert result["inserted"] == 1
    assert result["quarantine"] == 1
    assert result["status"] == "COMPLETADA"
    summary = fetch_summary(db_path)
    assert summary == {"clean": 1, "quarantine": 1}


def test_batch_rolls_back_and_records_failed_execution(tmp_path):
    db_path = tmp_path / "rollback.sqlite"
    initialize_database(db_path)
    connection = sqlite3.connect(str(db_path))
    connection.execute(
        """
        CREATE TRIGGER reject_second_transaction
        BEFORE INSERT ON transacciones_limpias
        WHEN NEW.id_transaccion = 'ATM-SECOND'
        BEGIN
            SELECT RAISE(ABORT, 'simulated persistence failure');
        END;
        """
    )
    connection.commit()
    connection.close()

    clean = [
        {"id_transaccion": "ATM-FIRST", "monto_mxn": 100},
        {"id_transaccion": "ATM-SECOND", "monto_mxn": 200},
    ]
    with pytest.raises(sqlite3.IntegrityError, match="simulated persistence failure"):
        persist_batch(db_path, "ATM", clean, [])

    connection = sqlite3.connect(str(db_path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM transacciones_limpias"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT estado FROM ejecuciones"
        ).fetchone()[0] == "FALLIDA"
    finally:
        connection.close()


def test_internal_exact_duplicates_are_logged_once(tmp_path):
    db_path = tmp_path / "duplicates.sqlite"
    record = {
        "id_transaccion": "ATM-200",
        "id_cuenta": "CTA-0001",
        "monto_mxn": 25,
    }

    result = persist_batch(db_path, "ATM", [record, record], [])

    assert result["inserted"] == 1
    assert result["internal_duplicates"] == 1
    assert result["read"] == result["inserted"] + result["internal_duplicates"]
    connection = sqlite3.connect(str(db_path))
    try:
        assert connection.execute(
            "SELECT resultado FROM filas_omitidas"
        ).fetchone()[0] == "DUPLICADO_INTERNO"
        assert connection.execute(
            "SELECT COUNT(*) FROM bitacora_duplicados"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_conflicting_ids_within_batch_are_quarantined_without_insertion(tmp_path):
    db_path = tmp_path / "conflicting-batch.sqlite"
    records = [
        {"id_transaccion": "ATM-300", "id_cuenta": "CTA-0001", "monto_mxn": 25},
        {"id_transaccion": "ATM-300", "id_cuenta": "CTA-0001", "monto_mxn": 35},
    ]

    result = persist_batch(db_path, "ATM", records, [])

    assert result["inserted"] == 0
    assert result["quarantine"] == 2
    connection = sqlite3.connect(str(db_path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM transacciones_limpias"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM cuarentena_errores "
            "WHERE codigo_error = 'ID_DUPLICADO_CONFLICTIVO'"
        ).fetchone()[0] == 2
    finally:
        connection.close()


def test_global_duplicate_is_skipped_but_conflict_is_quarantined(tmp_path):
    db_path = tmp_path / "global-duplicates.sqlite"
    original = {
        "id_transaccion": "ATM-400",
        "id_cuenta": "CTA-0001",
        "monto_mxn": 25,
    }
    persist_batch(db_path, "ATM", [original], [])

    repeated = persist_batch(db_path, "ATM", [original], [])
    conflicting = persist_batch(
        db_path,
        "ATM",
        [{"id_transaccion": "ATM-400", "id_cuenta": "CTA-0001", "monto_mxn": 40}],
        [],
    )

    assert repeated["already_loaded"] == 1
    assert repeated["inserted"] == 0
    assert conflicting["quarantine"] == 1
    assert fetch_summary(db_path) == {"clean": 1, "quarantine": 1}


def test_identical_confirmed_load_returns_previous_summary(tmp_path):
    db_path = tmp_path / "idempotent.sqlite"
    record = {"id_transaccion": "ATM-500", "id_cuenta": "CTA-0001", "monto_mxn": 10}
    first = persist_batch(db_path, "ATM", [record], [], identity_hash="sha256:batch")
    repeated = persist_batch(
        db_path,
        "ATM",
        [{"id_transaccion": "ATM-501", "monto_mxn": 99}],
        [],
        identity_hash="sha256:batch",
    )

    assert repeated["already_processed"] is True
    assert repeated["execution_id"] == first["execution_id"]
    assert repeated["inserted"] == 1
    assert fetch_summary(db_path) == {"clean": 1, "quarantine": 0}


def test_load_identity_uses_source_file_hashes_and_versions():
    original = build_load_identity(
        "ATM",
        {"transactions.csv": "hash-a", "catalog.csv": "hash-b"},
        "catalog-v1",
        "rules-v1",
        "process-v1",
    )
    reordered_files = build_load_identity(
        "ATM",
        {"renamed-transactions.csv": "hash-a", "renamed-catalog.csv": "hash-b"},
        "catalog-v1",
        "rules-v1",
        "process-v1",
    )
    changed_rules = build_load_identity(
        "ATM",
        {"transactions.csv": "hash-a", "catalog.csv": "hash-b"},
        "catalog-v1",
        "rules-v2",
        "process-v1",
    )

    assert original == reordered_files
    assert original != changed_rules


def test_catalog_version_and_account_are_stored_atomically(tmp_path):
    db_path = tmp_path / "catalog.sqlite"

    store_catalog_version(
        db_path,
        "catalog-v1",
        "sha256:catalog",
        [{"id_cuenta": "CTA-0001", "estado_cuenta": "ACTIVA"}],
    )

    connection = initialize_database(db_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM catalogo_cuentas WHERE version_catalogo = ?",
            ("catalog-v1",),
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_catalog_version_rolls_back_when_any_account_is_invalid(tmp_path):
    db_path = tmp_path / "invalid-catalog.sqlite"

    with pytest.raises(sqlite3.IntegrityError):
        store_catalog_version(
            db_path,
            "catalog-invalid",
            "sha256:invalid",
            [
                {"id_cuenta": "CTA-0001", "estado_cuenta": "ACTIVA"},
                {"id_cuenta": "CTA-0001", "estado_cuenta": "BLOQUEADA"},
            ],
        )

    connection = sqlite3.connect(str(db_path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM catalogo_versiones"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM catalogo_cuentas"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_clean_row_must_reference_account_in_selected_catalog_version(tmp_path):
    db_path = tmp_path / "catalog-fk.sqlite"
    store_catalog_version(
        db_path,
        "catalog-v1",
        "sha256:catalog",
        [{"id_cuenta": "CTA-0001", "estado_cuenta": "ACTIVA"}],
    )

    with pytest.raises(sqlite3.IntegrityError):
        persist_batch(
            db_path,
            "ATM",
            [{"id_transaccion": "ATM-600", "id_cuenta": "CTA-9999", "monto_mxn": 20}],
            [],
            metadata={"catalog_version": "catalog-v1"},
        )

    connection = sqlite3.connect(str(db_path))
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM transacciones_limpias"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT estado FROM ejecuciones"
        ).fetchone()[0] == "FALLIDA"
    finally:
        connection.close()
