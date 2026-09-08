from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.logging import get_logger


logger = get_logger(__name__)


def _get_database_url(settings: Settings) -> str:
    if settings.ENVIRONMENT == "test":
        database_url = settings.TEST_DATABASE_URL
    else:
        database_url = settings.DATABASE_URL

    if not database_url:
        variable_name = (
            "TEST_DATABASE_URL"
            if settings.ENVIRONMENT == "test"
            else "DATABASE_URL"
        )
        raise ValueError(f"Debe configurarse {variable_name} para PostgreSQL")

    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            "DATABASE_URL debe usar el formato "
            "postgresql+asyncpg://usuario:contraseña@host:puerto/base"
        )

    return database_url


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Crea el engine asíncrono de PostgreSQL."""

    database_url = _get_database_url(settings)
    return create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Crea la fábrica de sesiones para las dependencias de FastAPI."""

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def initialize_database(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Inicializa el engine y la fábrica de sesiones de PostgreSQL."""

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    logger.info("Engine de PostgreSQL inicializado")
    return engine, session_factory


async def check_database_connection(engine: AsyncEngine) -> None:
    """Comprueba que PostgreSQL responda."""

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def create_auth_session_table(engine: AsyncEngine) -> None:
    """Crea la tabla inicial de sesiones si todavía no existe."""
    from app.domains.auth.models import AuthSession
    from app.domains.users.models import User

    _ = User
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: AuthSession.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Proporciona una sesión SQLAlchemy por solicitud."""

    session_factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state,
        "db_session_factory",
        None,
    )
    if session_factory is None:
        raise RuntimeError("La fábrica de sesiones no está inicializada")

    async with session_factory() as session:
        yield session


async def close_database(engine: AsyncEngine) -> None:
    """Cierra el pool de conexiones de PostgreSQL."""

    await engine.dispose()
