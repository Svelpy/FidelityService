from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.routes import router
from app.domains.config_puntos.schemas import ConfigPuntosResponse
from app.domains.config_puntos.services import ConfigPuntosService
from app.shared.enums import EstadoConfigPuntos, Role
from app.shared.schemas.pagination import PaginatedResponse


def _config() -> ConfigPuntos:
    return ConfigPuntos(
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        asignacion_bolivianos=100,
        asignacion_puntos=10,
        costo_vale_bolivianos=50,
        costo_vale_puntos=500,
        status=EstadoConfigPuntos.ACTIVE,
    )


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
    app.include_router(router)
    current_user = CurrentUser(
        id=uuid4(),
        role=Role.SUPERADMIN,
        sucursal_id=None,
    )
    db_session = MagicMock(spec=AsyncSession)

    async def override_principal() -> CurrentUser:
        return current_user

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        yield client, current_user, db_session


def test_get_active_devuelve_configuracion_vigente(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    config = _config()

    with patch.object(
        ConfigPuntosService,
        "get_active",
        new=AsyncMock(return_value=config),
    ) as service:
        response = client.get("/config-puntos/active")

    assert response.status_code == 200
    assert response.json()["id"] == str(config.id)
    service.assert_awaited_once_with(db_session)


def test_list_devuelve_historial(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    config = _config()
    page = PaginatedResponse[ConfigPuntosResponse](
        total=1,
        page=1,
        per_page=10,
        total_pages=1,
        data=[config],
    )

    with patch.object(
        ConfigPuntosService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get("/config-puntos/?page=1&per_page=10")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    service.assert_awaited_once_with(db_session, page=1, per_page=10)


def test_replace_devuelve_201_y_delega_operandos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    config = _config()

    with patch.object(
        ConfigPuntosService,
        "replace",
        new=AsyncMock(return_value=config),
    ) as service:
        response = client.post(
            "/config-puntos/",
            json={
                "asignacion": {"bolivianos": 100, "puntos": 10},
                "costo_vale": {"bolivianos": 50, "puntos": 500},
            },
        )

    assert response.status_code == 201
    args = service.await_args
    assert args.args[0] is db_session
    assert args.args[1].asignacion.bolivianos == 100
    assert args.args[1].costo_vale.puntos == 500
    assert args.kwargs == {"actor_id": current_user.id}


def test_get_devuelve_configuracion_por_id(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    config = _config()

    with patch.object(
        ConfigPuntosService,
        "get",
        new=AsyncMock(return_value=config),
    ) as service:
        response = client.get(f"/config-puntos/{config.id}")

    assert response.status_code == 200
    service.assert_awaited_once_with(db_session, config.id)


def test_replace_rechaza_operandos_invalidos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    response = client.post(
        "/config-puntos/",
        json={
            "asignacion": {"bolivianos": 0, "puntos": 10},
            "costo_vale": {"bolivianos": 50, "puntos": 500},
        },
    )

    assert response.status_code == 422
