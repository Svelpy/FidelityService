import re
from datetime import date, datetime, timezone


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
