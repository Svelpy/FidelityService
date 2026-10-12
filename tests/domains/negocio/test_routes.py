from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.negocio.models import Negocio
from app.domains.negocio.routes import router
from app.domains.negocio.schemas import NegocioResponse
from app.domains.negocio.services import NegocioService
from app.shared.enums import Role, TipoNegocio
from app.shared.schemas.pagination import PaginatedResponse


def _negocio() -> Negocio:
    return Negocio(
        nombre="Café Central",
        tipo=TipoNegocio.SOCIO,
        descripcion="Cafetería artesanal.",
        telefono="71234567",
        image_url=None,
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
    settings = MagicMock(spec=Settings)

    async def override_principal() -> CurrentUser:
        return current_user

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        yield client, current_user, db_session


def test_list_negocios_delega_filtros(route_context: tuple[TestClient, CurrentUser, MagicMock]) -> None:
    client, _, db_session = route_context
    negocio = _negocio()
    page = PaginatedResponse[NegocioResponse](
        total=1,
        page=1,
        per_page=10,
        total_pages=1,
        data=[negocio],
    )

    with patch.object(
        NegocioService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get("/negocios/?page=1&per_page=10&tipo=SOCIO")

    assert response.status_code == 200
    assert response.json()["data"][0]["tipo"] == "SOCIO"
    service.assert_awaited_once_with(
        db_session,
        page=1,
        per_page=10,
        tipo=TipoNegocio.SOCIO,
    )


def test_create_negocio_devuelve_201(route_context: tuple[TestClient, CurrentUser, MagicMock]) -> None:
    client, current_user, db_session = route_context
    negocio = _negocio()

    with patch.object(
        NegocioService,
        "create",
        new=AsyncMock(return_value=negocio),
    ) as service:
        response = client.post(
            "/negocios/",
            json={"nombre": "Café Central", "tipo": "SOCIO"},
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(negocio.id)
    args = service.await_args
    assert args.args[0] is db_session
    assert args.args[1].nombre == "Café Central"
    assert args.kwargs == {"actor_id": current_user.id}


def test_get_negocio_devuelve_detalle(route_context: tuple[TestClient, CurrentUser, MagicMock]) -> None:
    client, _, db_session = route_context
    negocio = _negocio()

    with patch.object(
        NegocioService,
        "get",
        new=AsyncMock(return_value=negocio),
    ) as service:
        response = client.get(f"/negocios/{negocio.id}")

    assert response.status_code == 200
    assert response.json()["nombre"] == negocio.nombre
    service.assert_awaited_once_with(db_session, negocio.id)


def test_update_negocio_delega_patch(route_context: tuple[TestClient, CurrentUser, MagicMock]) -> None:
    client, current_user, db_session = route_context
    negocio = _negocio()

    with patch.object(
        NegocioService,
        "update",
        new=AsyncMock(return_value=negocio),
    ) as service:
        response = client.patch(
            f"/negocios/{negocio.id}",
            json={"descripcion": None},
        )

    assert response.status_code == 200
    args = service.await_args
    assert args.args[:2] == (db_session, negocio.id)
    assert args.args[2].model_dump(exclude_unset=True) == {"descripcion": None}
    assert args.kwargs == {"actor_id": current_user.id}


def test_delete_negocio_devuelve_204(route_context: tuple[TestClient, CurrentUser, MagicMock]) -> None:
    client, current_user, db_session = route_context
    negocio_id = uuid4()

    with patch.object(
        NegocioService,
        "delete",
        new=AsyncMock(),
    ) as service:
        response = client.delete(f"/negocios/{negocio_id}")

    assert response.status_code == 204
    assert response.content == b""
    service.assert_awaited_once_with(
        db_session,
        negocio_id,
        actor_id=current_user.id,
    )


def test_upload_negocio_image_acepta_multipart(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    negocio = _negocio()

    with patch.object(
        NegocioService,
        "upload_image",
        new=AsyncMock(return_value=negocio),
    ) as service:
        response = client.post(
            f"/negocios/{negocio.id}/image",
            files={"file": ("logo.png", b"png", "image/png")},
        )

    assert response.status_code == 200
    args = service.await_args
    assert args.args[:2] == (db_session, negocio.id)
    assert args.args[2].filename == "logo.png"
    assert args.kwargs["actor_id"] == current_user.id
    assert isinstance(args.kwargs["settings"], MagicMock)


def test_delete_negocio_image_delega_service(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    negocio = _negocio()

    with patch.object(
        NegocioService,
        "delete_image",
        new=AsyncMock(return_value=negocio),
    ) as service:
        response = client.delete(f"/negocios/{negocio.id}/image")

    assert response.status_code == 200
    service.assert_awaited_once_with(
        db_session,
        negocio.id,
        actor_id=current_user.id,
    )


def test_list_negocios_valida_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    response = client.get("/negocios/?page=0")

    assert response.status_code == 422
