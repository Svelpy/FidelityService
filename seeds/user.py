import asyncio
import logging
from pathlib import Path

from beanie import init_beanie
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.domains import all_models
from app.domains.users import User
from app.domains.users.schemas import UserCreate
from app.shared.enums import Role


class SeedSettings(BaseSettings):
    """Configuración exclusiva para ejecutar los seeds."""

    MONGODB_URL: str
    MONGODB_DB_NAME: str

    SEED_ADMIN_EMAIL_1: str
    SEED_ADMIN_NAME_1: str
    SEED_ADMIN_LASTNAME_1: str
    SEED_ADMIN_USERNAME_1: str
    SEED_ADMIN_PASSWORD_1: str

    SEED_ADMIN_EMAIL_2: str
    SEED_ADMIN_NAME_2: str
    SEED_ADMIN_LASTNAME_2: str
    SEED_ADMIN_USERNAME_2: str
    SEED_ADMIN_PASSWORD_2: str

    SEED_ADMIN_EMAIL_3: str
    SEED_ADMIN_NAME_3: str
    SEED_ADMIN_LASTNAME_3: str
    SEED_ADMIN_USERNAME_3: str
    SEED_ADMIN_PASSWORD_3: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def build_seed_admins(settings: SeedSettings) -> list[UserCreate]:
    """Valida y normaliza la configuración de los tres SUPERADMIN."""
    admins: list[UserCreate] = []

    for position in (1, 2, 3):
        try:
            admin = UserCreate(
                email=getattr(settings, f"SEED_ADMIN_EMAIL_{position}"),
                name=getattr(settings, f"SEED_ADMIN_NAME_{position}"),
                lastname=getattr(settings, f"SEED_ADMIN_LASTNAME_{position}"),
                username=getattr(settings, f"SEED_ADMIN_USERNAME_{position}"),
                password=getattr(settings, f"SEED_ADMIN_PASSWORD_{position}"),
                role=Role.SUPERADMIN,
            )
        except ValidationError as error:
            raise ValueError(
                f"Configuración inválida para SEED_ADMIN_*_{position}."
            ) from error

        if not admin.username:
            raise ValueError(
                f"SEED_ADMIN_USERNAME_{position} es obligatorio."
            )

        admins.append(admin)

    emails = [str(admin.email).lower() for admin in admins]
    usernames = [admin.username for admin in admins]
    if len(set(emails)) != len(emails):
        raise ValueError("Los emails de los SUPERADMIN deben ser únicos.")
    if len(set(usernames)) != len(usernames):
        raise ValueError("Los usernames de los SUPERADMIN deben ser únicos.")

    return admins


async def seed_users(settings: SeedSettings) -> None:
    """Crea los SUPERADMIN faltantes sin duplicar ni sobrescribir usuarios."""
    mongodb_client = AsyncMongoClient(
        settings.MONGODB_URL,
        tz_aware=True,
    )
    database = mongodb_client.get_database(settings.MONGODB_DB_NAME)

    try:
        await database.command("ping")
        await init_beanie(
            database=database,
            document_models=all_models,
        )

        admins = build_seed_admins(settings)
        created_count = 0

        for admin_data in admins:
            email = str(admin_data.email).strip().lower()
            username = admin_data.username

            existing_by_email = await User.find_one(User.email == email)
            existing_by_username = await User.find_one(User.username == username)

            if (
                existing_by_username is not None
                and (
                    existing_by_email is None
                    or existing_by_username.id != existing_by_email.id
                )
            ):
                raise ValueError(
                    f"El username configurado para el seed ya pertenece a otro usuario."
                )

            if existing_by_email is not None:
                if existing_by_email.role != Role.SUPERADMIN:
                    raise ValueError(
                        "El email configurado ya existe con un rol diferente a SUPERADMIN."
                    )
                logger.info("SUPERADMIN existente omitido; no se sobrescribió su contraseña.")
                continue

            user = User(
                email=email,
                name=admin_data.name,
                lastname=admin_data.lastname,
                username=username,
                password_hash=hash_password(admin_data.password),
                role=Role.SUPERADMIN,
                business_id=None,
            )

            try:
                await user.insert()
            except DuplicateKeyError as error:
                raise ValueError(
                    "No se pudo crear un SUPERADMIN porque email o username ya existe."
                ) from error

            created_count += 1

        logger.info(
            "Seed finalizado: %s SUPERADMIN nuevos; existentes conservados.",
            created_count,
        )

    except Exception:
        logger.exception("Error durante la ejecución del seed")
        raise
    finally:
        await mongodb_client.close()


if __name__ == "__main__":
    asyncio.run(seed_users(SeedSettings()))
