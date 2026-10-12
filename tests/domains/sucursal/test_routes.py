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
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.routes import router
from app.domains.sucursal.schemas import SucursalResponse
from app.domains.sucursal.services import SucursalService
from app.shared.enums import Role
from app.shared.schemas.pagination import PaginatedResponse


def _sucursal() -> Sucursal:
    return Sucursal(
        nombre="Sucursal Equipetrol",
        negocio_id=uuid4(),
        direccion="Av. San Martín 123",
        url_ubicacion="https://maps.google.com/?q=-17.77,-63.20",
        telefono="71234567",
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


def test_list_sucursales_delega_filtros(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    sucursal = _sucursal()
    page = PaginatedResponse[SucursalResponse](
        total=1,
        page=1,
        per_page=10,
        total_pages=1,
        data=[sucursal],
    )

    with patch.object(
        SucursalService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get(
            f"/sucursales/?page=1&per_page=10&negocio_id={sucursal.negocio_id}"
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["nombre"] == sucursal.nombre
    service.assert_awaited_once_with(
        db_session,
        page=1,
        per_page=10,
        negocio_id=sucursal.negocio_id,
    )


def test_create_sucursal_devuelve_201(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    sucursal = _sucursal()

    with patch.object(
        SucursalService,
        "create",
        new=AsyncMock(return_value=sucursal),
    ) as service:
        response = client.post(
            "/sucursales/",
            json={
                "nombre": sucursal.nombre,
                "negocio_id": str(sucursal.negocio_id),
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(sucursal.id)
    args = service.await_args
    assert args.args[0] is db_session
    assert args.args[1].negocio_id == sucursal.negocio_id
    assert args.kwargs == {"actor_id": current_user.id}


def test_get_sucursal_devuelve_detalle(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    sucursal = _sucursal()

    with patch.object(
        SucursalService,
        "get",
        new=AsyncMock(return_value=sucursal),
    ) as service:
        response = client.get(f"/sucursales/{sucursal.id}")

    assert response.status_code == 200
    assert response.json()["nombre"] == sucursal.nombre
    service.assert_awaited_once_with(db_session, sucursal.id)


def test_update_sucursal_delega_patch(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    sucursal = _sucursal()

    with patch.object(
        SucursalService,
        "update",
        new=AsyncMock(return_value=sucursal),
    ) as service:
        response = client.patch(
            f"/sucursales/{sucursal.id}",
            json={"direccion": None},
        )

    assert response.status_code == 200
    args = service.await_args
    assert args.args[:2] == (db_session, sucursal.id)
    assert args.args[2].model_dump(exclude_unset=True) == {"direccion": None}
    assert args.kwargs == {"actor_id": current_user.id}


def test_delete_sucursal_devuelve_204(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    sucursal_id = uuid4()

    with patch.object(
        SucursalService,
        "delete",
        new=AsyncMock(),
    ) as service:
        response = client.delete(f"/sucursales/{sucursal_id}")

    assert response.status_code == 204
    assert response.content == b""
    service.assert_awaited_once_with(
        db_session,
        sucursal_id,
        actor_id=current_user.id,
    )


def test_list_sucursales_valida_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    response = client.get("/sucursales/?page=0")

    assert response.status_code == 422
