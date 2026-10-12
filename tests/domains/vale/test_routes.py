from collections.abc import AsyncGenerator
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
from app.domains.vale.models import Vale
from app.domains.vale.routes import router
from app.domains.vale.schemas import ValePuntosSuggestionResponse
from app.domains.vale.services import ValeService
from app.shared.enums import Role


def _vale() -> Vale:
    return Vale(
        total_costo=Decimal("50.00"),
        total_puntos=450,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
    app.include_router(router)
    current_user = CurrentUser(id=uuid4(), role=Role.SUPERADMIN, sucursal_id=None)
    db_session = MagicMock(spec=AsyncSession)

    async def principal() -> CurrentUser:
        return current_user

    async def database() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = principal
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, current_user, db_session


def test_suggest_points_solo_devuelve_valor_sugerido(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    with patch.object(
        ValeService,
        "suggest_points",
        new=AsyncMock(return_value=ValePuntosSuggestionResponse(puntos_sugeridos=500)),
    ) as service:
        response = client.post("/vales/sugerir-puntos", json={"total_costo": "50.00"})
    assert response.status_code == 200
    assert response.json() == {"puntos_sugeridos": 500}
    service.assert_awaited_once_with(db_session, Decimal("50.00"))


def test_create_acepta_puntos_distintos_a_sugerencia(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    vale = _vale()
    with patch.object(ValeService, "create", new=AsyncMock(return_value=vale)) as service:
        response = client.post(
            "/vales/",
            json={
                "total_costo": "50.00",
                "total_puntos": 450,
                "nombre": "Vale Bs 50",
                "categoria_id": str(vale.categoria_id),
                "negocio_id": str(vale.negocio_id),
            },
        )
    assert response.status_code == 201
    assert response.json()["total_puntos"] == 450
    assert service.await_args.kwargs == {"actor_id": current_user.id}
    assert service.await_args.args[0] is db_session


def test_get_delega_al_servicio(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    vale = _vale()
    with patch.object(ValeService, "get", new=AsyncMock(return_value=vale)) as service:
        response = client.get(f"/vales/{vale.id}")
    assert response.status_code == 200
    service.assert_awaited_once_with(db_session, vale.id)


def test_delete_devuelve_204(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    vale_id = uuid4()
    with patch.object(ValeService, "delete", new=AsyncMock()) as service:
        response = client.delete(f"/vales/{vale_id}")
    assert response.status_code == 204
    service.assert_awaited_once_with(db_session, vale_id, current_user.id)
