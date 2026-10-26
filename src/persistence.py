from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator


_NON_ORIGIN_FIELDS = {
    "id_lote",
    "ejecucion_id",
    "archivo_origen",
    "fila_origen",
    "fuente",
    "origen_ingreso",
    "fecha_procesado",
    "fecha_procesamiento",
    "transformaciones_aplicadas",
    "monto_analitico_mxn",
    "monto_normalizado",
    "segmento",
    "es_outlier",
    "limite_inferior",
    "limite_superior",
    "diferencia_capping",
    "estado_cuenta",
    "titular",
    "tipo_cuenta",
    "limite_credito_mxn",
    "fecha_apertura",
    "tasa_conversion",
    "version_catalogo",
    "version_reglas",
    "version_proceso",
}


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Tipo no serializable en JSON: {type(value).__name__}")


def _json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    )


def _source_record(record: dict[str, Any]) -> dict[str, Any]:
    original = record.get("registro_origen", record.get("original_record"))
    if isinstance(original, dict):
        return original
    return {key: value for key, value in record.items() if key not in _NON_ORIGIN_FIELDS}


def _source_fingerprint(record: dict[str, Any]) -> str:
    payload = _json_dumps(_source_record(record))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_load_identity(
    source: str,
    file_hashes: dict[str, str],
    catalog_version: str | None,
    rules_version: str,
    process_version: str,
) -> str:
    identity = {
        "source": source,
        "file_hashes": sorted(file_hashes.values()),
        "catalog_version": catalog_version,
        "rules_version": rules_version,
        "process_version": process_version,
    }
    return "sha256:" + hashlib.sha256(_json_dumps(identity).encode("utf-8")).hexdigest()


def _transaction_id(record: dict[str, Any]) -> str:
    value = record.get("id_transaccion") or record.get("transfer_id")
    if value is None or str(value).strip() == "":
        raise ValueError("Cada transacción limpia debe tener un identificador.")
    return str(value).strip()


def _account_id(record: dict[str, Any]) -> str | None:
    value = record.get("id_cuenta") or record.get("account_id")
    return str(value).strip() if value is not None and str(value).strip() else None


def _insert_execution(
    connection: sqlite3.Connection,
    source: str,
    execution_id: str,
    identity_hash: str | None,
    metadata: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO ejecuciones (
            id, fuente, identidad_carga, hash_archivos, version_catalogo,
            version_reglas, version_proceso, estado, filas_leidas,
            nuevas_limpias, cuarentena, duplicados_internos, ya_cargadas
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'EN_PROCESO', 0, 0, 0, 0, 0)
        """,
        (
            execution_id,
            source,
            identity_hash,
            _json_dumps(metadata.get("file_hashes", {})),
            metadata.get("catalog_version"),
            metadata.get("rules_version"),
            metadata.get("process_version"),
        ),
    )


def initialize_database(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalogo_versiones (
            version TEXT PRIMARY KEY,
            hash_contenido TEXT NOT NULL UNIQUE,
            fecha_carga TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS catalogo_cuentas (
            version_catalogo TEXT NOT NULL,
            id_cuenta TEXT NOT NULL,
            atributos_json TEXT NOT NULL,
            PRIMARY KEY (version_catalogo, id_cuenta),
            FOREIGN KEY (version_catalogo)
                REFERENCES catalogo_versiones(version) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS ejecuciones (
            id TEXT PRIMARY KEY,
            fuente TEXT NOT NULL,
            identidad_carga TEXT,
            hash_archivos TEXT NOT NULL DEFAULT '{}',
            version_catalogo TEXT,
            version_reglas TEXT,
            version_proceso TEXT,
            estado TEXT NOT NULL CHECK (
                estado IN ('EN_PROCESO', 'COMPLETADA', 'FALLIDA', 'SIN_REGISTROS')
            ),
            filas_leidas INTEGER NOT NULL DEFAULT 0,
            nuevas_limpias INTEGER NOT NULL DEFAULT 0,
            cuarentena INTEGER NOT NULL DEFAULT 0,
            duplicados_internos INTEGER NOT NULL DEFAULT 0,
            ya_cargadas INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            iniciada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finalizada_en TEXT,
            FOREIGN KEY (version_catalogo)
                REFERENCES catalogo_versiones(version) ON DELETE RESTRICT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ux_ejecuciones_identidad_confirmada
            ON ejecuciones(fuente, identidad_carga)
            WHERE identidad_carga IS NOT NULL AND estado = 'COMPLETADA';

        CREATE TABLE IF NOT EXISTS transacciones_limpias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente TEXT NOT NULL,
            id_transaccion TEXT NOT NULL,
            id_cuenta TEXT,
            ejecucion_id TEXT,
            version_catalogo TEXT,
            huella_origen TEXT,
            registro_origen TEXT,
            payload TEXT NOT NULL,
            fecha_procesado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fuente, id_transaccion),
            FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id) ON DELETE RESTRICT,
            FOREIGN KEY (version_catalogo)
                REFERENCES catalogo_versiones(version) ON DELETE RESTRICT,
            FOREIGN KEY (version_catalogo, id_cuenta)
                REFERENCES catalogo_cuentas(version_catalogo, id_cuenta)
                ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS cuarentena_errores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente TEXT NOT NULL,
            id_transaccion TEXT,
            ejecucion_id TEXT,
            archivo_origen TEXT,
            fila_origen TEXT,
            motivo_rechazo_cuarentena TEXT NOT NULL,
            codigo_error TEXT NOT NULL,
            detalles_errores TEXT NOT NULL DEFAULT '[]',
            campo_afectado TEXT,
            original_record TEXT NOT NULL,
            fase TEXT NOT NULL DEFAULT 'VALIDACION',
            estado_seguimiento TEXT NOT NULL DEFAULT 'ABIERTA'
                CHECK (estado_seguimiento IN ('ABIERTA', 'RESUELTA')),
            fecha_procesado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS filas_omitidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ejecucion_id TEXT NOT NULL,
            fuente TEXT NOT NULL,
            id_transaccion TEXT,
            resultado TEXT NOT NULL CHECK (
                resultado IN ('DUPLICADO_INTERNO', 'YA_CARGADA')
            ),
            transaccion_existente_id INTEGER,
            archivo_origen TEXT,
            fila_origen TEXT,
            registro_origen TEXT NOT NULL,
            fecha_procesado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id) ON DELETE RESTRICT,
            FOREIGN KEY (transaccion_existente_id)
                REFERENCES transacciones_limpias(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS bitacora_duplicados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ejecucion_id TEXT NOT NULL,
            fuente TEXT NOT NULL,
            id_transaccion TEXT,
            tipo_duplicado TEXT NOT NULL,
            registro_origen TEXT NOT NULL,
            fecha_procesado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id) ON DELETE RESTRICT
        );
        """
    )
    connection.commit()
    return connection


@contextmanager
def transactional_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = initialize_database(db_path)
    try:
        connection.execute("BEGIN")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def store_catalog_version(
    db_path: str | Path,
    version: str,
    content_hash: str,
    accounts: list[dict[str, Any]],
) -> None:
    connection = initialize_database(db_path)
    try:
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO catalogo_versiones (version, hash_contenido) VALUES (?, ?)",
            (version, content_hash),
        )
        for account in accounts:
            account_id = account.get("id_cuenta")
            if account_id is None or not str(account_id).strip():
                raise ValueError("Cada cuenta de catálogo debe tener id_cuenta.")
            connection.execute(
                """
                INSERT INTO catalogo_cuentas (version_catalogo, id_cuenta, atributos_json)
                VALUES (?, ?, ?)
                """,
                (version, str(account_id).strip(), _json_dumps(account)),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def insert_clean_record(
    connection: sqlite3.Connection,
    fuente: str,
    record: dict[str, Any],
    execution_id: str | None = None,
    catalog_version: str | None = None,
) -> int:
    origin = _source_record(record)
    cursor = connection.execute(
        """
        INSERT INTO transacciones_limpias (
            fuente, id_transaccion, id_cuenta, ejecucion_id, version_catalogo,
            huella_origen, registro_origen, payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fuente,
            _transaction_id(record),
            _account_id(record),
            execution_id,
            catalog_version,
            _source_fingerprint(record),
            _json_dumps(origin),
            _json_dumps(record),
        ),
    )
    return int(cursor.lastrowid)


def insert_quarantine_record(
    connection: sqlite3.Connection,
    fuente: str,
    original_record: dict[str, Any],
    reasons: Iterable[str],
    campo_afectado: str | None = None,
    execution_id: str | None = None,
    phase: str = "VALIDACION",
    error_details: list[dict[str, Any]] | None = None,
) -> int:
    reason_list = sorted(set(reasons))
    if not reason_list:
        raise ValueError("Un registro de cuarentena debe tener al menos un motivo.")
    motivo = "; ".join(reason_list)
    transaction_id = (
        original_record.get("id_transaccion")
        or original_record.get("transfer_id")
        or None
    )
    cursor = connection.execute(
        """
        INSERT INTO cuarentena_errores (
            fuente, id_transaccion, ejecucion_id, archivo_origen, fila_origen,
            motivo_rechazo_cuarentena, codigo_error, detalles_errores,
            campo_afectado, original_record, fase
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fuente,
            str(transaction_id) if transaction_id is not None else None,
            execution_id,
            original_record.get("archivo_origen"),
            str(original_record["fila_origen"])
            if original_record.get("fila_origen") is not None
            else None,
            motivo,
            reason_list[0],
            _json_dumps(error_details or []),
            campo_afectado,
            _json_dumps(original_record),
            phase,
        ),
    )
    return int(cursor.lastrowid)


def _insert_omitted(
    connection: sqlite3.Connection,
    execution_id: str,
    source: str,
    record: dict[str, Any],
    result: str,
    existing_id: int | None = None,
) -> None:
    transaction_id = record.get("id_transaccion") or record.get("transfer_id")
    connection.execute(
        """
        INSERT INTO filas_omitidas (
            ejecucion_id, fuente, id_transaccion, resultado,
            transaccion_existente_id, archivo_origen, fila_origen, registro_origen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            execution_id,
            source,
            str(transaction_id) if transaction_id is not None else None,
            result,
            existing_id,
            record.get("archivo_origen"),
            str(record["fila_origen"]) if record.get("fila_origen") is not None else None,
            _json_dumps(_source_record(record)),
        ),
    )
    if result == "DUPLICADO_INTERNO":
        connection.execute(
            """
            INSERT INTO bitacora_duplicados (
                ejecucion_id, fuente, id_transaccion, tipo_duplicado, registro_origen
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                source,
                str(transaction_id) if transaction_id is not None else None,
                result,
                _json_dumps(_source_record(record)),
            ),
        )


def persist_batch(
    db_path: str | Path,
    source: str,
    clean_records: list[dict[str, Any]],
    quarantine_records: list[dict[str, Any]],
    *,
    identity_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    connection = initialize_database(db_path)
    try:
        if identity_hash:
            previous = connection.execute(
                """
                SELECT id, filas_leidas, nuevas_limpias, cuarentena,
                       duplicados_internos, ya_cargadas
                FROM ejecuciones
                WHERE fuente = ? AND identidad_carga = ? AND estado = 'COMPLETADA'
                """,
                (source, identity_hash),
            ).fetchone()
            if previous:
                return {
                    "execution_id": previous["id"],
                    "status": "OMITIDA_IDENTICA",
                    "already_processed": True,
                    "read": previous["filas_leidas"],
                    "inserted": previous["nuevas_limpias"],
                    "quarantine": previous["cuarentena"],
                    "internal_duplicates": previous["duplicados_internos"],
                    "already_loaded": previous["ya_cargadas"],
                }

        execution_id = str(uuid.uuid4())
        _insert_execution(connection, source, execution_id, identity_hash, metadata)
        connection.commit()
    finally:
        connection.close()

    counts = {
        "read": len(clean_records) + len(quarantine_records),
        "inserted": 0,
        "quarantine": 0,
        "internal_duplicates": 0,
        "already_loaded": 0,
    }
    try:
        with transactional_connection(db_path) as connection:
            catalog_version = metadata.get("catalog_version")
            grouped: dict[str, list[dict[str, Any]]] = {}
            for record in clean_records:
                grouped.setdefault(_transaction_id(record), []).append(record)

            candidate_records: list[dict[str, Any]] = []
            for transaction_id, records in grouped.items():
                fingerprints = {_source_fingerprint(record) for record in records}
                if len(fingerprints) > 1:
                    for record in records:
                        insert_quarantine_record(
                            connection,
                            source,
                            record,
                            ["ID_DUPLICADO_CONFLICTIVO"],
                            execution_id=execution_id,
                            phase="DEDUPLICACION",
                        )
                        counts["quarantine"] += 1
                    continue
                candidate_records.append(records[0])
                for duplicate in records[1:]:
                    _insert_omitted(
                        connection,
                        execution_id,
                        source,
                        duplicate,
                        "DUPLICADO_INTERNO",
                    )
                    counts["internal_duplicates"] += 1

            for record in candidate_records:
                transaction_id = _transaction_id(record)
                existing = connection.execute(
                    """
                    SELECT id, huella_origen, registro_origen
                    FROM transacciones_limpias
                    WHERE fuente = ? AND id_transaccion = ?
                    """,
                    (source, transaction_id),
                ).fetchone()
                fingerprint = _source_fingerprint(record)
                if existing:
                    existing_fingerprint = existing["huella_origen"]
                    if existing_fingerprint is None:
                        existing_fingerprint = hashlib.sha256(
                            existing["registro_origen"].encode("utf-8")
                        ).hexdigest()
                    if existing_fingerprint == fingerprint:
                        _insert_omitted(
                            connection,
                            execution_id,
                            source,
                            record,
                            "YA_CARGADA",
                            existing["id"],
                        )
                        counts["already_loaded"] += 1
                    else:
                        insert_quarantine_record(
                            connection,
                            source,
                            record,
                            ["ID_DUPLICADO_CONFLICTIVO"],
                            execution_id=execution_id,
                            phase="DEDUPLICACION",
                        )
                        counts["quarantine"] += 1
                    continue

                insert_clean_record(
                    connection,
                    source,
                    record,
                    execution_id,
                    catalog_version,
                )
                counts["inserted"] += 1

            for item in quarantine_records:
                insert_quarantine_record(
                    connection,
                    source,
                    item["record"],
                    item.get("reasons", []),
                    item.get("campo_afectado"),
                    execution_id,
                    item.get("fase", "VALIDACION"),
                    item.get("detalles_errores"),
                )
                counts["quarantine"] += 1

            connection.execute(
                """
                UPDATE ejecuciones
                SET estado = ?, filas_leidas = ?, nuevas_limpias = ?, cuarentena = ?,
                    duplicados_internos = ?, ya_cargadas = ?, finalizada_en = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    "SIN_REGISTROS" if counts["read"] == 0 else "COMPLETADA",
                    counts["read"],
                    counts["inserted"],
                    counts["quarantine"],
                    counts["internal_duplicates"],
                    counts["already_loaded"],
                    execution_id,
                ),
            )
        return {
            "execution_id": execution_id,
            "status": "SIN_REGISTROS" if counts["read"] == 0 else "COMPLETADA",
            "already_processed": False,
            **counts,
        }
    except Exception as exc:
        failure_connection = sqlite3.connect(str(db_path))
        try:
            failure_connection.execute(
                """
                UPDATE ejecuciones
                SET estado = 'FALLIDA', error = ?, finalizada_en = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (f"{type(exc).__name__}: {exc}", execution_id),
            )
            failure_connection.commit()
        finally:
            failure_connection.close()
        raise


def fetch_summary(db_path: str | Path) -> dict[str, int]:
    connection = sqlite3.connect(str(db_path))
    try:
        clean_count = connection.execute(
            "SELECT COUNT(*) FROM transacciones_limpias"
        ).fetchone()[0]
        quarantine_count = connection.execute(
            "SELECT COUNT(*) FROM cuarentena_errores"
        ).fetchone()[0]
    finally:
        connection.close()
    return {"clean": clean_count, "quarantine": quarantine_count}
