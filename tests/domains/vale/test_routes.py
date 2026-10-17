from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.categoria.models import Categoria
from app.domains.negocio.models import Negocio
from app.domains.sucursal.models import Sucursal
from app.domains.vale.models import Vale
from app.domains.vale.routes import router
from app.domains.vale.schemas import (
    ValeDetailResponse,
    ValeDetailResponseAudit,
    ValeListResponse,
    ValePuntosSuggestionResponse,
)
from app.domains.vale.services import ValeService
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Role, TipoNegocio
from app.shared.schemas.pagination import PaginatedResponse


def _vale() -> Vale:
    return Vale(
        total_costo=Decimal("50.00"),
        total_puntos=450,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )


def _negocio(vale: Vale) -> Negocio:
    return Negocio(id=vale.negocio_id, nombre="Café Central", tipo=TipoNegocio.SOCIO)


def _categoria(vale: Vale) -> Categoria:
    return Categoria(
        id=vale.categoria_id,
        nombre="Gastronomía",
        slug="gastronomia",
        icon_number=3,
    )


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
    register_exception_handlers(app, get_settings())
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
            data={
                "total_costo": "50.00",
                "total_puntos": "450",
                "nombre": "Vale Bs 50",
                "categoria_id": str(vale.categoria_id),
                "negocio_id": str(vale.negocio_id),
            },
            files={"image": ("vale.png", b"image", "image/png")},
        )
    assert response.status_code == 201
    assert response.json()["total_puntos"] == 450
    assert service.await_args.kwargs == {
        "actor_id": current_user.id,
        "image": ANY,
        "settings": ANY,
    }
    assert service.await_args.args[0] is db_session


def test_create_devuelve_422_ante_validacion_invalida_del_schema(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    with patch.object(ValeService, "create", new=AsyncMock()) as service:
        response = client.post(
            "/vales/",
            data={
                "total_costo": "0",
                "total_puntos": "450",
                "nombre": "Vale Bs 50",
                "categoria_id": str(uuid4()),
                "negocio_id": str(uuid4()),
            },
        )

    assert response.status_code == 422
    service.assert_not_awaited()


def test_update_acepta_campos_e_imagen_en_form_data(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    vale = _vale()
    with patch.object(ValeService, "update", new=AsyncMock(return_value=vale)) as service:
        response = client.patch(
            f"/vales/{vale.id}",
            data={
                "nombre": "Vale actualizado",
                "total_puntos": "500",
                "descripcion": "",
            },
            files={"image": ("vale.png", b"image", "image/png")},
        )
    assert response.status_code == 200
    submitted = service.await_args.args[2]
    assert submitted.model_dump(exclude_unset=True) == {
        "total_puntos": 500,
        "nombre": "Vale actualizado",
        "descripcion": None,
    }
    assert service.await_args.kwargs == {
        "actor_id": current_user.id,
        "image": ANY,
        "settings": ANY,
    }
    assert service.await_args.args[:2] == (db_session, vale.id)


def test_update_devuelve_422_ante_validacion_invalida_del_schema(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context
    vale_id = uuid4()

    with patch.object(ValeService, "update", new=AsyncMock()) as service:
        response = client.patch(
            f"/vales/{vale_id}",
            data={"total_puntos": "-500"},
        )

    assert response.status_code == 422
    service.assert_not_awaited()


def test_update_ignora_campos_no_nullable_vacios_del_form_data(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context
    vale = _vale()

    with patch.object(ValeService, "update", new=AsyncMock(return_value=vale)) as service:
        response = client.patch(
            f"/vales/{vale.id}",
            data={
                "nombre": "Vale actualizado",
                "total_costo": "",
                "total_puntos": "",
                "categoria_id": "",
                "negocio_id": "",
            },
        )

    assert response.status_code == 200
    submitted = service.await_args.args[2]
    assert submitted.model_dump(exclude_unset=True) == {
        "nombre": "Vale actualizado"
    }


def test_update_no_ignora_cero_explicito_del_form_data(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    with patch.object(ValeService, "update", new=AsyncMock()) as service:
        response = client.patch(
            f"/vales/{uuid4()}",
            data={"total_costo": "0"},
        )

    assert response.status_code == 422
    service.assert_not_awaited()


def test_list_devuelve_vale_con_negocio_y_categoria(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context
    vale = _vale()
    page = PaginatedResponse[ValeListResponse](
        total=1,
        page=1,
        per_page=20,
        total_pages=1,
        data=[
            ValeListResponse(
                vale=vale,
                negocio=_negocio(vale),
                categoria=_categoria(vale),
            )
        ],
    )
    with patch.object(ValeService, "list", new=AsyncMock(return_value=page)):
        response = client.get("/vales/")
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert set(item) == {"vale", "negocio", "categoria"}
    assert item["negocio"]["id"] == str(vale.negocio_id)
    assert item["categoria"]["id"] == str(vale.categoria_id)


def test_get_delega_al_servicio(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, db_session = route_context
    vale = _vale()
    negocio = _negocio(vale)
    detail = ValeDetailResponse(
        vale=vale,
        categoria=_categoria(vale),
        negocio=negocio,
        sucursales=[Sucursal(nombre="Sucursal Centro", negocio_id=negocio.id)],
    )
    with patch.object(
        ValeService,
        "get_detail",
        new=AsyncMock(return_value=detail),
    ) as service:
        response = client.get(f"/vales/{vale.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["vale"]["id"] == str(vale.id)
    assert body["negocio"]["id"] == str(negocio.id)
    assert len(body["sucursales"]) == 1
    assert body["categoria"]["id"] == str(vale.categoria_id)
    service.assert_awaited_once_with(db_session, vale.id)


@pytest.mark.parametrize("role", [Role.SUPERADMIN, Role.OWNER, Role.ADMIN])
def test_get_audit_permite_roles_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, current_user, db_session = route_context
    current_user.role = role
    vale = _vale()
    negocio = _negocio(vale)
    detail = ValeDetailResponseAudit(
        vale=vale,
        categoria=_categoria(vale),
        negocio=negocio,
        sucursales=[Sucursal(nombre="Sucursal Centro", negocio_id=negocio.id)],
    )

    with patch.object(
        ValeService,
        "get_detail_audit",
        new=AsyncMock(return_value=detail),
    ) as service:
        response = client.get(f"/vales/{vale.id}/audit")

    assert response.status_code == 200
    assert response.json()["vale"]["id"] == str(vale.id)
    service.assert_awaited_once_with(db_session, vale.id)


@pytest.mark.parametrize("role", [Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_get_audit_rechaza_roles_no_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, current_user, _ = route_context
    current_user.role = role

    with patch.object(ValeService, "get_detail_audit", new=AsyncMock()) as service:
        response = client.get(f"/vales/{uuid4()}/audit")

    assert response.status_code == 403
    service.assert_not_awaited()


def test_delete_devuelve_204(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, current_user, db_session = route_context
    vale_id = uuid4()
    with patch.object(ValeService, "delete", new=AsyncMock()) as service:
        response = client.delete(f"/vales/{vale_id}")
    assert response.status_code == 204
    service.assert_awaited_once_with(db_session, vale_id, current_user.id)
