import asyncio

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.database import (
    check_database_connection,
    close_database,
    initialize_database,
)
from app.core.logging import get_logger, setup_logging
from app.core.security import hash_password
import app.domains.model_registry  # noqa: F401
from app.domains.users.models import User
from app.shared.enums import Genero, Role
from app.shared.services.validators import (
    validator_ci,
    validator_email,
    validator_name,
    validator_password,
    validator_phone,
)


logger = get_logger(__name__)


class SeedAdminData(BaseModel):
    ci: str = Field(min_length=6, max_length=20)
    telefono: str = Field(min_length=6, max_length=20)
    nombre: str = Field(min_length=2, max_length=60)
    apellidos: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    @field_validator("ci", mode="before")
    @classmethod
    def validate_ci(cls, value: object) -> str:
        return validator_ci(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str:
        return validator_phone(value)

    @field_validator("nombre", "apellidos", mode="before")
    @classmethod
    def validate_names(cls, value: object) -> str:
        return validator_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> str:
        return validator_password(value)


def build_seed_admins(settings: Settings) -> list[SeedAdminData]:
    """Valida y normaliza la configuración de los tres SUPERADMIN."""
    admins: list[SeedAdminData] = []

    for position in (1, 2, 3):
        password = getattr(settings, f"SEED_ADMIN_PASSWORD_{position}")
        try:
            admin = SeedAdminData(
                ci=getattr(settings, f"SEED_ADMIN_CI_{position}"),
                telefono=getattr(settings, f"SEED_ADMIN_PHONE_{position}"),
                nombre=getattr(settings, f"SEED_ADMIN_NAME_{position}"),
                apellidos=getattr(settings, f"SEED_ADMIN_LASTNAME_{position}"),
                email=getattr(settings, f"SEED_ADMIN_EMAIL_{position}"),
                password=password.get_secret_value() if password is not None else None,
            )
        except ValidationError as error:
            raise ValueError(
                f"Configuración inválida para SEED_ADMIN_*_{position}: {error}"
            ) from error

        admins.append(admin)

    cis = [admin.ci for admin in admins]
    emails = [str(admin.email) for admin in admins]
    if len(set(cis)) != len(cis):
        raise ValueError("Las cédulas configuradas para los SUPERADMIN deben ser únicas.")
    if len(set(emails)) != len(emails):
        raise ValueError("Los emails configurados para los SUPERADMIN deben ser únicos.")

    return admins


async def seed_users(settings: Settings) -> None:
    """Crea los tres SUPERADMIN faltantes sin sobrescribir los existentes."""
    admins = build_seed_admins(settings)
    engine, session_factory = initialize_database(settings)

    try:
        await check_database_connection(engine)

        async with session_factory() as db_session:
            created_count = 0

            for position, admin_data in enumerate(admins, start=1):
                result = await db_session.execute(
                    select(User).where(User.ci == admin_data.ci)
                )
                existing_user = result.scalar_one_or_none()

                if existing_user is not None:
                    if existing_user.is_deleted:
                        raise ValueError(
                            f"SEED_ADMIN_*_{position} pertenece a un usuario eliminado."
                        )
                    if existing_user.role != Role.SUPERADMIN:
                        raise ValueError(
                            f"SEED_ADMIN_*_{position} ya existe con otro rol."
                        )

                    logger.info(
                        "SUPERADMIN %s existente; no se sobrescribió su contraseña.",
                        position,
                    )
                    continue

                password_hash = await asyncio.to_thread(
                    hash_password,
                    admin_data.password,
                )
                user = User(
                    ci=admin_data.ci,
                    telefono=admin_data.telefono,
                    nombre=admin_data.nombre,
                    apellidos=admin_data.apellidos,
                    email=str(admin_data.email),
                    password_hash=password_hash,
                    role=Role.SUPERADMIN,
                    genero=Genero.O,
                    puntos=0,
                    sucursal_id=None,
                    is_deleted=False,
                )
                user.created_by = user.id
                user.updated_by = user.id
                db_session.add(user)
                created_count += 1

            try:
                await db_session.commit()
            except IntegrityError as error:
                await db_session.rollback()
                raise ValueError(
                    "No se pudieron crear los SUPERADMIN por un conflicto de integridad."
                ) from error

            logger.info(
                "Seed finalizado: %s SUPERADMIN nuevos; %s existentes conservados.",
                created_count,
                len(admins) - created_count,
            )
    except Exception:
        logger.exception("Error durante la ejecución del seed de usuarios")
        raise
    finally:
        await close_database(engine)


if __name__ == "__main__":
    app_settings = get_settings()
    setup_logging(app_settings)
    asyncio.run(seed_users(app_settings))
