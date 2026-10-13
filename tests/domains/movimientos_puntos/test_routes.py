from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.movimientos_puntos.routes import router
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.shared.enums import Role, TipoMovimiento
from app.shared.schemas.pagination import PaginatedResponse


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


def _empty_page(*, page: int, per_page: int) -> PaginatedResponse:
    return PaginatedResponse(
        total=0,
        page=page,
        per_page=per_page,
        total_pages=0,
        data=[],
    )


def test_get_me_delega_usuario_actual_y_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    with patch.object(
        MovimientoPuntosService,
        "list_for_user",
        new=AsyncMock(return_value=_empty_page(page=2, per_page=10)),
    ) as service:
        response = client.get(
            "/movimientos-puntos/me",
            params={"page": 2, "per_page": 10, "tipo": "CANJE"},
        )

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        principal.id,
        page=2,
        per_page=10,
        movement_type=TipoMovimiento.CANJE,
    )


def test_get_by_user_id_delega_rol_y_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.CAJERO
    user_id = uuid4()
    with patch.object(
        MovimientoPuntosService,
        "list_by_user_id",
        new=AsyncMock(return_value=_empty_page(page=1, per_page=20)),
    ) as service:
        response = client.get(f"/movimientos-puntos/{user_id}")

    assert response.status_code == 200
    service.assert_awaited_once_with(
        session,
        user_id,
        principal.role,
        page=1,
        per_page=20,
        movement_type=None,
    )
