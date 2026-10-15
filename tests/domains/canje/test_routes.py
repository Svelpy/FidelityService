from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.canje.models import Canje
from app.domains.canje.routes import router
from app.domains.canje.schemas import CanjeExpireResponse, CanjeResponse
from app.domains.canje.services import CanjeService
from app.shared.enums import EstadoCanje, Role
from app.shared.schemas.pagination import PaginatedResponse


def _redemption() -> Canje:
    return Canje(
        cliente_id=uuid4(),
        dador_id=None,
        vale_id=uuid4(),
        status=EstadoCanje.PENDIENTE,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        codigo_canje="00123456",
        sucursal_id=None,
        total_puntos=500,
        total_costo=Decimal("50.00"),
        referencia=None,
        config_punto_id=uuid4(),
    )


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
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


def test_create_delega_cliente_y_expiracion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    redemption = _redemption()
    with patch.object(
        CanjeService,
        "create",
        new=AsyncMock(return_value=redemption),
    ) as service:
        response = client.post(
            "/canjes/",
            json={
                "vale_id": str(redemption.vale_id),
                "referencia": None,
            },
        )

    assert response.status_code == 201
    assert service.await_args.args[0] is session
    assert service.await_args.args[2:] == (
        principal.id,
        principal.role,
    )


def test_list_delega_todos_los_filtros(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    redemption = _redemption()
    dador_id = uuid4()
    sucursal_id = uuid4()
    page = PaginatedResponse[CanjeResponse](
        total=1,
        page=2,
        per_page=10,
        total_pages=1,
        data=[redemption],
    )
    with patch.object(
        CanjeService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get(
            "/canjes/",
            params={
                "page": 2,
                "per_page": 10,
                "cliente_id": str(redemption.cliente_id),
                "dador_id": str(dador_id),
                "vale_id": str(redemption.vale_id),
                "status": EstadoCanje.CANJEADO.value,
                "sucursal_id": str(sucursal_id),
            },
        )

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        principal.id,
        principal.role,
        principal.sucursal_id,
        page=2,
        per_page=10,
        cliente_id=redemption.cliente_id,
        dador_id=dador_id,
        vale_id=redemption.vale_id,
        status=EstadoCanje.CANJEADO,
        sucursal_id=sucursal_id,
    )


@pytest.mark.parametrize(
    "filter_name",
    ["cliente_id", "dador_id", "vale_id", "sucursal_id"],
)
def test_list_rechaza_ids_de_filtro_invalidos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    filter_name: str,
) -> None:
    client, _, _ = route_context

    assert client.get("/canjes/", params={filter_name: "invalido"}).status_code == 422


def test_list_me_delega_usuario_y_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    page = PaginatedResponse[CanjeResponse](
        total=0,
        page=2,
        per_page=10,
        total_pages=0,
        data=[],
    )
    with patch.object(
        CanjeService,
        "list_for_user",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get("/canjes/me", params={"page": 2, "per_page": 10})

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        principal.id,
        page=2,
        per_page=10,
    )


def test_redeem_delega_codigo_y_sucursal(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.CAJERO
    principal.sucursal_id = uuid4()
    redemption = _redemption()
    with patch.object(
        CanjeService,
        "redeem",
        new=AsyncMock(return_value=redemption),
    ) as service:
        response = client.post(
            "/canjes/redeem",
            json={"codigo_canje": "00123456"},
        )

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        "00123456",
        principal.id,
        principal.role,
        principal.sucursal_id,
    )


def test_expire_delega_actor_autenticado(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    with patch.object(
        CanjeService,
        "expire_pending",
        new=AsyncMock(return_value=CanjeExpireResponse(expired_count=3)),
    ) as service:
        response = client.post("/canjes/expire")

    assert response.status_code == 200
    assert response.json() == {"expired_count": 3}
    service.assert_awaited_once_with(session, actor_id=principal.id)


def test_cancel_delega_identidad_del_cajero(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.CAJERO
    principal.sucursal_id = uuid4()
    redemption = _redemption()
    with patch.object(
        CanjeService,
        "cancel",
        new=AsyncMock(return_value=redemption),
    ) as service:
        response = client.post(f"/canjes/{redemption.id}/cancel")

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        redemption.id,
        principal.id,
        principal.role,
    )
