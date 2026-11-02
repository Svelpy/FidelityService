from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.categoria.routes import router as categoria_router
from app.domains.categoria.schemas import CategoriaResponseAudit
from app.domains.categoria.services import CategoriaService
from app.domains.config_puntos.routes import router as config_puntos_router
from app.domains.config_puntos.schemas import ConfigPuntosResponseAudit
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.routes import router as movimientos_puntos_router
from app.domains.movimientos_puntos.schemas import MovimientoPuntosResponseAudit
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.routes import router as negocio_router
from app.domains.negocio.schemas import NegocioResponseAudit
from app.domains.negocio.services import NegocioService
from app.domains.sucursal.routes import router as sucursal_router
from app.domains.sucursal.schemas import SucursalResponseAudit
from app.domains.sucursal.services import SucursalService
from app.domains.users.routes import router as users_router
from app.domains.users.schemas import UserResponseAudit
from app.domains.users.services import UserService
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Role


AUDIT_FIELDS = {"created_by", "updated_by", "is_deleted", "deleted_at", "deleted_by"}

# (router, prefijo, service, schema plano de auditoría)
AUDIT_ENDPOINTS = [
    (categoria_router, "/categorias", CategoriaService, CategoriaResponseAudit),
    (config_puntos_router, "/config-puntos", ConfigPuntosService, ConfigPuntosResponseAudit),
    (
        movimientos_puntos_router,
        "/movimientos-puntos",
        MovimientoPuntosService,
        MovimientoPuntosResponseAudit,
    ),
    (negocio_router, "/negocios", NegocioService, NegocioResponseAudit),
    (sucursal_router, "/sucursales", SucursalService, SucursalResponseAudit),
    (users_router, "/users", UserService, UserResponseAudit),
]
ENDPOINT_IDS = [prefix for _, prefix, _, _ in AUDIT_ENDPOINTS]


def _client(router: APIRouter, role: Role) -> tuple[TestClient, MagicMock]:
    app = FastAPI()
    register_exception_handlers(app, get_settings())
    app.include_router(router)
    db_session = MagicMock(spec=AsyncSession)

    async def principal() -> CurrentUser:
        return CurrentUser(id=uuid4(), role=role, sucursal_id=None)

    async def database() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = principal
    app.dependency_overrides[get_db] = database
    return TestClient(app), db_session


def _deleted_record(schema: type[BaseModel]) -> BaseModel:
    record = schema.model_validate(schema.model_json_schema()["example"])
    return record.model_copy(
        update={
            "is_deleted": True,
            "deleted_at": datetime.now(timezone.utc),
            "deleted_by": uuid4(),
        }
    )


@pytest.mark.parametrize(
    ("router", "prefix", "service", "schema"),
    AUDIT_ENDPOINTS,
    ids=ENDPOINT_IDS,
)
def test_audit_devuelve_schema_plano_incluyendo_eliminados(
    router: APIRouter,
    prefix: str,
    service: type,
    schema: type[BaseModel],
) -> None:
    client, db_session = _client(router, Role.SUPERADMIN)
    record = _deleted_record(schema)

    with patch.object(service, "get", new=AsyncMock(return_value=record)) as get:
        response = client.get(f"{prefix}/{record.id}/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == set(schema.model_fields)
    assert AUDIT_FIELDS <= set(body)
    assert body["is_deleted"] is True
    assert not any(isinstance(value, (dict, list)) for value in body.values())
    get.assert_awaited_once_with(db_session, record.id, include_deleted=True)


@pytest.mark.parametrize(
    ("router", "prefix", "service", "schema"),
    AUDIT_ENDPOINTS,
    ids=ENDPOINT_IDS,
)
@pytest.mark.parametrize(
    "role",
    [Role.OWNER, Role.ADMIN, Role.CAJERO, Role.SOCIO, Role.CLIENTE],
)
def test_audit_solo_permite_superadmin(
    router: APIRouter,
    prefix: str,
    service: type,
    schema: type[BaseModel],
    role: Role,
) -> None:
    client, _ = _client(router, role)

    with patch.object(service, "get", new=AsyncMock()) as get:
        response = client.get(f"{prefix}/{uuid4()}/audit")

    assert response.status_code == 403
    get.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service", "column"),
    [
        (ConfigPuntosService, "config_puntos.is_deleted"),
        (MovimientoPuntosService, "movimientos_puntos.is_deleted"),
    ],
    ids=["config_puntos", "movimientos_puntos"],
)
@pytest.mark.parametrize(
    ("include_deleted", "filtra_eliminados"),
    [(False, True), (True, False)],
)
async def test_get_solo_incluye_eliminados_si_se_pide(
    service: type,
    column: str,
    include_deleted: bool,
    filtra_eliminados: bool,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = object()
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    await service.get(session, uuid4(), include_deleted=include_deleted)

    statement = session.execute.await_args.args[0]
    assert (column in str(statement.whereclause)) is filtra_eliminados
