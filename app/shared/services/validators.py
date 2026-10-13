import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.shared.services.slug import generate_slug


def validator_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("El nombre debe ser texto.")
    normalized_name = value.strip()
    if not re.fullmatch(r"^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'-]+$", normalized_name):
        raise ValueError(
            "El nombre solo permite letras, espacios, guiones y apóstrofes."
        )
    return normalized_name


def validator_phone(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("El número de teléfono debe ser texto.")
    normalized_phone = value.strip()
    if not re.fullmatch(r"\d{6,20}", normalized_phone):
        raise ValueError(
            "El número de teléfono debe tener entre 6 y 20 dígitos."
        )
    return normalized_phone


def validator_ci(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("La cédula de identidad debe ser texto.")
    normalized_ci = value.strip()
    if not re.fullmatch(r"\d{6,20}", normalized_ci):
        raise ValueError(
            "La cédula de identidad debe tener entre 6 y 20 dígitos."
        )
    return normalized_ci


def validator_password(value: object) -> str:
    # Por el tipo de aplicación no se exige una complejidad alta.
    if not isinstance(value, str):
        raise ValueError("La contraseña debe ser texto.")
    if len(value) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    if len(value) > 20:
        raise ValueError("La contraseña debe tener menos de 20 caracteres.")
    return value


def validator_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("El email debe ser texto.")
    return value.strip().lower()


def validator_birth_date(value: object) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("La fecha de nacimiento debe ser una fecha válida.")
    if value > datetime.now(timezone.utc).date():
        raise ValueError("La fecha de nacimiento no puede ser futura.")
    return value


def validator_address(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("La dirección debe ser texto.")
    normalized_address = value.strip()
    if not normalized_address:
        raise ValueError("La dirección no puede estar vacía.")
    return normalized_address


def validator_text(value: object) -> str:
    """Normaliza texto libre, incluido el texto vacío."""
    if not isinstance(value, str):
        raise ValueError("El valor debe ser texto.")
    return value.strip()


def validator_non_empty_text(value: object) -> str:
    """Normaliza texto libre y rechaza valores vacíos."""
    normalized_text = validator_text(value)
    if not normalized_text:
        raise ValueError("El texto no puede estar vacío.")
    return normalized_text


def validator_redemption_code(value: object) -> str:
    """Normaliza y valida un código de canje de exactamente ocho dígitos."""
    if not isinstance(value, str):
        raise ValueError("El código de canje debe ser texto.")
    normalized_code = value.strip()
    if re.fullmatch(r"[0-9]{8}", normalized_code) is None:
        raise ValueError(
            "El código de canje debe contener exactamente ocho dígitos."
        )
    return normalized_code


def validator_http_url(value: object) -> str:
    """Normaliza una URL HTTP(S) absoluta."""
    if not isinstance(value, str):
        raise ValueError("La URL debe ser texto.")
    normalized_url = value.strip()
    parsed_url = urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("La URL debe ser una dirección HTTP o HTTPS válida.")
    return normalized_url


def validator_slug_source(value: object) -> str:
    """Valida texto no vacío capaz de producir un slug."""
    normalized_text = validator_non_empty_text(value)
    if not generate_slug(normalized_text):
        raise ValueError("El texto debe contener al menos una letra o un número válido.")
    return normalized_text


def validator_non_negative_integer(value: object) -> int:
    """Valida un entero mayor o igual a cero sin aceptar booleanos."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("El valor debe ser un número entero.")
    if value < 0:
        raise ValueError("El valor debe ser mayor o igual a cero.")
    return value


def validator_positive_integer(value: object) -> int:
    """Valida un entero positivo sin aceptar booleanos."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("El valor debe ser un número entero.")
    if value <= 0:
        raise ValueError("El valor debe ser mayor que cero.")
    return value


def validator_positive_money(value: object) -> Decimal:
    """Convierte un importe finito y positivo a Decimal."""
    if isinstance(value, bool) or not isinstance(
        value,
        (Decimal, int, float, str),
    ):
        raise ValueError("El importe debe ser un número válido.")
    if isinstance(value, str) and not value.strip():
        raise ValueError("El importe no puede estar vacío.")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError("El importe debe ser un número válido.") from error
    if not amount.is_finite():
        raise ValueError("El importe debe ser finito.")
    if amount <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    return amount
