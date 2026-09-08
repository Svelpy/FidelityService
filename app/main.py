from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import (
    check_database_connection,
    close_database,
    create_auth_session_table,
    initialize_database,
)
from app.core.logging import setup_logging
from app.integrations.cloudinary import configure_cloudinary
from app.integrations.redis import create_redis_client
from app.middlewares import register_all_middlewares
from app.api import api_router

settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa y libera los recursos de la aplicación."""
    configure_cloudinary(settings)

    database_engine = None
    session_factory = None
    redis_client = None

    try:
        database_engine, session_factory = initialize_database(settings)
        await check_database_connection(database_engine)
        await create_auth_session_table(database_engine)

        redis_client = create_redis_client(settings)
        await redis_client.ping()

        app.state.database = database_engine
        app.state.db_session_factory = session_factory
        app.state.redis_client = redis_client
        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()

        if database_engine is not None:
            await close_database(database_engine)


# Crear aplicación
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Registrar middlewares
register_all_middlewares(app,settings)

# Registrar routers
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
