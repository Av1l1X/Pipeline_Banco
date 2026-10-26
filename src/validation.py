from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    ValidationError,
    ValidationInfo,
    field_validator,
)

ATM_TIPO_OPERACION = Literal["RETIRO", "DEPOSITO", "PAGO_SERVICIOS", "CONSULTA_SALDO"]
ATM_ESTADO = Literal["EXITOSA", "FALLO_FONDOS", "FALLO_CONEXION"]
DIGITAL_ESTADO = Literal["LIQUIDADA", "PENDIENTE", "RECHAZADA", "DEVUELTA"]
CURRENCY = Literal["MXN", "USD"]

UTC_MINUS_6 = timezone(timedelta(hours=-6))
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
_ISO_DATETIME_WITH_ZONE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_GROUPED_NUMBER = re.compile(
    r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?$"
)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _as_optional_decimal(value: Any, field_name: str) -> Decimal | None:
    if _missing(value):
        return None
    if isinstance(value, bool):
        raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}")
        try:
            result = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}") from exc
    else:
        text = str(value).strip()
        if _GROUPED_NUMBER.fullmatch(text):
            text = text.replace(",", "")
        elif not _NUMBER.fullmatch(text):
            raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}")
        try:
            result = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}") from exc
    if not result.is_finite():
        raise ValueError(f"FORMATO_NUMERICO_INVALIDO: {field_name}")
    return result


def _parse_iso(text: str, *, require_timezone: bool) -> datetime:
    valid_format = (
        _ISO_DATETIME_WITH_ZONE.fullmatch(text)
        if require_timezone
        else _ISO_DATETIME.fullmatch(text) or _ISO_DATE.fullmatch(text)
    )
    if not valid_format:
        raise ValueError("FECHA_INVALIDA")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC_MINUS_6)
        return parsed.astimezone(UTC_MINUS_6)
    except ValueError as exc:
        raise ValueError("FECHA_INVALIDA") from exc


def _parse_atm_datetime(value: Any) -> datetime:
    if _missing(value):
        raise ValueError("FECHA_INVALIDA")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        return _parse_iso(value.strip(), require_timezone=False)
    else:
        raise ValueError("FECHA_INVALIDA")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC_MINUS_6)
    return parsed.astimezone(UTC_MINUS_6)


def _parse_digital_datetime(value: Any) -> datetime:
    if _missing(value) or isinstance(value, bool):
        raise ValueError("FECHA_INVALIDA")
    if isinstance(value, (int, float, Decimal)):
        try:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("FECHA_INVALIDA")
            return datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone(UTC_MINUS_6)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("FECHA_INVALIDA") from exc
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("FECHA_INVALIDA")
        return value.astimezone(UTC_MINUS_6)
    if isinstance(value, str):
        return _parse_iso(value.strip(), require_timezone=True)
    raise ValueError("FECHA_INVALIDA")


def _required_identifier(value: Any) -> str:
    if _missing(value):
        raise ValueError("CAMPO_OBLIGATORIO_AUSENTE")
    return str(value).strip().upper()


def _optional_text(value: Any, default: str) -> str:
    if _missing(value):
        return default
    return str(value).strip()


class ATMTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id_transaccion: str
    fecha_hora: datetime
    id_cuenta: str
    tipo_operacion: ATM_TIPO_OPERACION
    monto_mxn: Decimal | None = None
    id_cajero: str = "DESCONOCIDO"
    resultado: ATM_ESTADO
    comision_aplicada: Decimal | None = None

    @field_validator("id_transaccion", "id_cuenta", mode="before")
    @classmethod
    def _normalize_identifiers(cls, value: Any) -> str:
        return _required_identifier(value)

    @field_validator("id_cajero", mode="before")
    @classmethod
    def _default_terminal_id(cls, value: Any) -> str:
        return _optional_text(value, "DESCONOCIDO").upper()

    @field_validator("tipo_operacion", "resultado", mode="before")
    @classmethod
    def _normalize_categories(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("fecha_hora", mode="before")
    @classmethod
    def _parse_fecha(cls, value: Any) -> datetime:
        return _parse_atm_datetime(value)

    @field_validator("monto_mxn", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> Decimal | None:
        return _as_optional_decimal(value, "monto_mxn")

    @field_validator("monto_mxn")
    @classmethod
    def _validate_amount(
        cls,
        value: Decimal | None,
        info: ValidationInfo,
    ) -> Decimal | None:
        operation = info.data.get("tipo_operacion")
        if value is None:
            return value
        if operation == "CONSULTA_SALDO" and value != Decimal("0"):
            raise ValueError("MONTO_INVALIDO")
        if operation != "CONSULTA_SALDO" and value <= 0:
            raise ValueError("MONTO_INVALIDO")
        return value

    @field_validator("comision_aplicada", mode="before")
    @classmethod
    def _parse_commission(cls, value: Any) -> Decimal | None:
        return _as_optional_decimal(value, "comision_aplicada")

    @field_validator("comision_aplicada")
    @classmethod
    def _validate_commission(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("COMISION_INVALIDA")
        return value


class DigitalTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    transfer_id: str
    timestamp: datetime
    account_id: str
    amount: Decimal | None = None
    currency: CURRENCY
    beneficiary_clabe: str
    notification_email: EmailStr | None = None
    concept: str = "SIN_CONCEPTO"
    status: DIGITAL_ESTADO
    platform: str

    @field_validator("transfer_id", "account_id", mode="before")
    @classmethod
    def _normalize_identifiers(cls, value: Any) -> str:
        return _required_identifier(value)

    @field_validator("concept", mode="before")
    @classmethod
    def _default_concept(cls, value: Any) -> str:
        return _optional_text(value, "SIN_CONCEPTO")

    @field_validator("platform", mode="before")
    @classmethod
    def _required_platform(cls, value: Any) -> str:
        if _missing(value):
            raise ValueError("CAMPO_OBLIGATORIO_AUSENTE")
        return str(value).strip()

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: Any) -> datetime:
        return _parse_digital_datetime(value)

    @field_validator("amount", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> Decimal | None:
        return _as_optional_decimal(value, "amount")

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("MONTO_INVALIDO")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> str:
        if _missing(value):
            raise ValueError("MONEDA_NO_ADMITIDA")
        return str(value).strip().upper()

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("beneficiary_clabe", mode="before")
    @classmethod
    def _validate_clabe(cls, value: Any) -> str:
        text = "" if _missing(value) else str(value).strip()
        if not re.fullmatch(r"[0-9]{18}", text, flags=re.ASCII):
            raise ValueError("CLABE_INVALIDA")
        return text

    @field_validator("notification_email", mode="before")
    @classmethod
    def _normalize_email(cls, value: Any) -> str | None:
        if _missing(value):
            return None
        return str(value).strip()

def validate_atm_record(raw: dict[str, Any]) -> tuple[ATMTransaction | None, list[str]]:
    model, details = validate_atm_record_detailed(raw)
    return model, sorted({item["codigo"] for item in details})


def validate_atm_record_detailed(
    raw: dict[str, Any],
) -> tuple[ATMTransaction | None, list[dict[str, str]]]:
    try:
        model = ATMTransaction.model_validate(raw)
        return model, []
    except ValidationError as exc:
        return None, _validation_error_details(exc)


def validate_digital_record(raw: dict[str, Any]) -> tuple[DigitalTransaction | None, list[str]]:
    model, details = validate_digital_record_detailed(raw)
    return model, sorted({item["codigo"] for item in details})


def validate_digital_record_detailed(
    raw: dict[str, Any],
) -> tuple[DigitalTransaction | None, list[dict[str, str]]]:
    try:
        model = DigitalTransaction.model_validate(raw)
        return model, []
    except ValidationError as exc:
        return None, _validation_error_details(exc)


_ERROR_DESCRIPTIONS = {
    "CAMPO_OBLIGATORIO_AUSENTE": "Falta un campo obligatorio para identificar o procesar la operación.",
    "CLABE_INVALIDA": "La CLABE debe contener exactamente 18 dígitos ASCII.",
    "MONEDA_NO_ADMITIDA": "La moneda debe ser MXN o USD.",
    "FECHA_INVALIDA": "La fecha no cumple el formato admitido o no representa una fecha válida.",
    "MONTO_INVALIDO": "El monto no cumple la regla de validez para el tipo de operación.",
    "COMISION_INVALIDA": "La comisión no puede ser negativa.",
    "FORMATO_NUMERICO_INVALIDO": "El valor debe ser un número decimal finito.",
    "CORREO_INVALIDO": "El correo no cumple la validación sintáctica.",
    "ESTADO_NO_ADMITIDO": "El estado de la operación no está admitido para esta fuente.",
    "OPERACION_NO_ADMITIDA": "El tipo de operación no está admitido para esta fuente.",
}

_FIELD_CODES = {
    "beneficiary_clabe": "CLABE_INVALIDA",
    "currency": "MONEDA_NO_ADMITIDA",
    "tipo_operacion": "OPERACION_NO_ADMITIDA",
    "resultado": "ESTADO_NO_ADMITIDO",
    "status": "ESTADO_NO_ADMITIDO",
    "fecha_hora": "FECHA_INVALIDA",
    "timestamp": "FECHA_INVALIDA",
    "notification_email": "CORREO_INVALIDO",
    "monto_mxn": "FORMATO_NUMERICO_INVALIDO",
    "amount": "FORMATO_NUMERICO_INVALIDO",
    "comision_aplicada": "FORMATO_NUMERICO_INVALIDO",
}

_REQUIRED_FIELDS = {
    "id_transaccion",
    "id_cuenta",
    "transfer_id",
    "account_id",
    "id_cajero",
    "concept",
    "platform",
}


def _validation_error_details(exc: ValidationError) -> list[dict[str, str]]:
    details: dict[tuple[str, str], dict[str, str]] = {}
    field_codes = {
        **_FIELD_CODES,
        "monto_mxn": "FORMATO_NUMERICO_INVALIDO",
        "amount": "FORMATO_NUMERICO_INVALIDO",
        "comision_aplicada": "FORMATO_NUMERICO_INVALIDO",
    }
    for error in exc.errors():
        location = error.get("loc", ())
        field = str(location[0]) if location else ""
        message = str(error.get("msg", ""))
        error_type = str(error.get("type", ""))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        message_codes = set(message.split("|"))
        known_codes = {
            "CAMPO_OBLIGATORIO_AUSENTE",
            "CLABE_INVALIDA",
            "MONEDA_NO_ADMITIDA",
            "FECHA_INVALIDA",
            "MONTO_INVALIDO",
            "COMISION_INVALIDA",
            "FORMATO_NUMERICO_INVALIDO",
        }
        if message_codes & known_codes:
            for code in message_codes & known_codes:
                error_field = field or _field_for_code(code)
                details[(error_field, code)] = {
                    "campo": error_field,
                    "codigo": code,
                    "descripcion": _ERROR_DESCRIPTIONS[code],
                }
            continue
        if message in {
            "CAMPO_OBLIGATORIO_AUSENTE",
            "CLABE_INVALIDA",
            "MONEDA_NO_ADMITIDA",
            "FECHA_INVALIDA",
            "MONTO_INVALIDO",
            "COMISION_INVALIDA",
            "FORMATO_NUMERICO_INVALIDO",
        }:
            details[(field, message)] = {
                "campo": field,
                "codigo": message,
                "descripcion": _ERROR_DESCRIPTIONS[message],
            }
        elif error_type == "missing":
            code = "CAMPO_OBLIGATORIO_AUSENTE"
            details[(field, code)] = {
                "campo": field,
                "codigo": code,
                "descripcion": _ERROR_DESCRIPTIONS[code],
            }
        elif field in field_codes:
            code = field_codes[field]
            if field in {"monto_mxn", "amount", "comision_aplicada"} and error_type not in {
                "value_error",
                "decimal_parsing",
            }:
                code = "FORMATO_NUMERICO_INVALIDO"
            details[(field, code)] = {
                "campo": field,
                "codigo": code,
                "descripcion": _ERROR_DESCRIPTIONS[code],
            }
        elif field in _REQUIRED_FIELDS:
            code = "CAMPO_OBLIGATORIO_AUSENTE"
            details[(field, code)] = {
                "campo": field,
                "codigo": code,
                "descripcion": _ERROR_DESCRIPTIONS[code],
            }
        else:
            code = error_type.upper() or "VALIDACION_ERROR"
            details[(field, code)] = {
                "campo": field,
                "codigo": code,
                "descripcion": message,
            }
    return sorted(details.values(), key=lambda item: (item["campo"], item["codigo"]))


def _field_for_code(code: str) -> str:
    fields_by_code = {
        "MONTO_INVALIDO": "monto_mxn",
        "COMISION_INVALIDA": "comision_aplicada",
    }
    return fields_by_code.get(code, "")


def _normalize_validation_errors(exc: ValidationError) -> list[str]:
    return sorted({item["codigo"] for item in _validation_error_details(exc)})
