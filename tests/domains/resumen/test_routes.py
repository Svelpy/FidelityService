from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.resumen.routes import router
from app.domains.resumen.schemas import (
    ResumenAdminResponse,
    ResumenCajeroResponse,
    ResumenClienteResponse,
)
from app.domains.resumen.services import ResumenService
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Role


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
    register_exception_handlers(app, get_settings())
    app.include_router(router)
    principal_value = CurrentUser(
        id=uuid4(),
        role=Role.CLIENTE,
        sucursal_id=None,
    )
    db_session = MagicMock(spec=AsyncSession)

    async def principal() -> CurrentUser:
        return principal_value

    async def database() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = principal
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, principal_value, db_session


def test_resumen_cliente_usa_usuario_en_sesion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    resumen = ResumenClienteResponse(
        nombre="Ana",
        puntos=750,
        nivel=ResumenService.calcular_nivel(750),
    )
    with patch.object(
        ResumenService,
        "get_cliente",
        new=AsyncMock(return_value=resumen),
    ) as service:
        response = client.get("/resumen/cliente")

    assert response.status_code == 200
    assert response.json() == resumen.model_dump(mode="json")
    service.assert_awaited_once_with(session, principal.id)


def test_resumen_cliente_rechaza_roles_no_cliente(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, _ = route_context
    principal.role = Role.CAJERO

    with patch.object(ResumenService, "get_cliente", new=AsyncMock()) as service:
        response = client.get("/resumen/cliente")

    assert response.status_code == 403
    service.assert_not_awaited()


def _admin_example() -> ResumenAdminResponse:
    return ResumenAdminResponse.model_validate(
        ResumenAdminResponse.model_json_schema()["example"]
    )


def _cajero_example() -> ResumenCajeroResponse:
    return ResumenCajeroResponse.model_validate(
        ResumenCajeroResponse.model_json_schema()["example"]
    )


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN])
def test_resumen_admin_permite_owner_y_admin(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, session = route_context
    principal.role = role
    resumen = _admin_example()

    with patch.object(
        ResumenService,
        "get_admin",
        new=AsyncMock(return_value=resumen),
    ) as service:
        response = client.get("/resumen/admin")

    assert response.status_code == 200
    assert response.json() == resumen.model_dump(mode="json")
    assert service.await_args.args[0] is session


@pytest.mark.parametrize(
    "role",
    [Role.CAJERO, Role.CLIENTE, Role.SOCIO, Role.SUPERADMIN],
)
def test_resumen_admin_rechaza_otros_roles(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, _ = route_context
    principal.role = role

    with patch.object(ResumenService, "get_admin", new=AsyncMock()) as service:
        response = client.get("/resumen/admin")

    assert response.status_code == 403
    service.assert_not_awaited()


def test_resumen_cajero_usa_usuario_en_sesion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.CAJERO
    resumen = _cajero_example()

    with patch.object(
        ResumenService,
        "get_cajero",
        new=AsyncMock(return_value=resumen),
    ) as service:
        response = client.get("/resumen/cajero")

    assert response.status_code == 200
    assert response.json() == resumen.model_dump(mode="json")
    assert service.await_args.args[:2] == (session, principal.id)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.CLIENTE, Role.SOCIO])
def test_resumen_cajero_rechaza_otros_roles(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, _ = route_context
    principal.role = role

    with patch.object(ResumenService, "get_cajero", new=AsyncMock()) as service:
        response = client.get("/resumen/cajero")

    assert response.status_code == 403
    service.assert_not_awaited()
