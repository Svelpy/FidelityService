from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.canje.models import Canje
from app.domains.canje.routes import router
from app.domains.canje.schemas import (
    CanjeDetailResponse,
    CanjeDetailResponseAudit,
    CanjeExpireResponse,
    CanjeListResponse,
)
from app.domains.canje.services import CanjeService
from app.domains.negocio.models import Negocio
from app.domains.users.models import User
from app.domains.vale.models import Vale
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import EstadoCanje, Genero, Role, TipoNegocio
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


def _voucher(redemption: Canje) -> Vale:
    return Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )


def _business(voucher: Vale) -> Negocio:
    return Negocio(
        id=voucher.negocio_id,
        nombre="Café Central",
        tipo=TipoNegocio.SOCIO,
    )


def _user(user_id: UUID) -> User:
    return User(
        id=user_id,
        nombre="Cliente",
        ci="12345678",
        telefono="71234567",
        role=Role.CLIENTE,
        genero=Genero.O,
        puntos=500,
        password_hash="hash",
    )


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
    voucher = _voucher(redemption)
    business = _business(voucher)
    dador_id = uuid4()
    sucursal_id = uuid4()
    negocio_id = uuid4()
    page = PaginatedResponse[CanjeListResponse](
        total=1,
        page=2,
        per_page=10,
        total_pages=1,
        data=[
            CanjeListResponse(
                canje=redemption,
                vale=voucher,
                sucursal=None,
                negocio=business,
            )
        ],
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
                "negocio_id": str(negocio_id),
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
        negocio_id=negocio_id,
    )


@pytest.mark.parametrize(
    "filter_name",
    ["cliente_id", "dador_id", "vale_id", "sucursal_id", "negocio_id"],
)
def test_list_rechaza_ids_de_filtro_invalidos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    filter_name: str,
) -> None:
    client, _, _ = route_context

    assert client.get("/canjes/", params={filter_name: "invalido"}).status_code == 422


@pytest.mark.parametrize("filter_name", ["vale_id", "negocio_id", "sucursal_id"])
def test_list_me_rechaza_ids_de_filtro_invalidos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    filter_name: str,
) -> None:
    client, _, _ = route_context

    assert client.get("/canjes/me", params={filter_name: "invalido"}).status_code == 422


def test_list_me_delega_usuario_y_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    redemption = _redemption()
    voucher = _voucher(redemption)
    business = _business(voucher)
    sucursal_id = uuid4()
    page = PaginatedResponse[CanjeListResponse](
        total=1,
        page=2,
        per_page=10,
        total_pages=1,
        data=[
            CanjeListResponse(
                canje=redemption,
                vale=voucher,
                sucursal=None,
                negocio=business,
            )
        ],
    )
    with patch.object(
        CanjeService,
        "list_for_user",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get(
            "/canjes/me",
            params={
                "page": 2,
                "per_page": 10,
                "status": EstadoCanje.PENDIENTE.value,
                "vale_id": str(redemption.vale_id),
                "negocio_id": str(business.id),
                "sucursal_id": str(sucursal_id),
            },
        )

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert set(item) == {"canje", "vale", "sucursal", "negocio"}
    assert item["sucursal"] is None
    assert item["negocio"]["id"] == str(business.id)
    for nested in (item["canje"], item["vale"], item["negocio"]):
        assert "created_at" in nested and "updated_at" in nested
        assert "created_by" not in nested and "is_deleted" not in nested
    service.assert_awaited_once_with(
        session,
        principal.id,
        page=2,
        per_page=10,
        status=EstadoCanje.PENDIENTE,
        vale_id=redemption.vale_id,
        negocio_id=business.id,
        sucursal_id=sucursal_id,
    )


def test_get_by_id_devuelve_canje_con_vale_auditados(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    redemption = _redemption()
    voucher = _voucher(redemption)
    business = _business(voucher)
    detail = CanjeDetailResponse(
        canje=redemption,
        usuario_cliente=_user(redemption.cliente_id),
        usuario_cajero_socio=None,
        vale=voucher,
        sucursal=None,
        negocio=business,
    )

    with patch.object(
        CanjeService,
        "get",
        new=AsyncMock(return_value=detail),
    ) as service:
        response = client.get(f"/canjes/{redemption.id}")

    assert response.status_code == 200
    assert response.json()["canje"]["id"] == str(redemption.id)
    assert response.json()["vale"]["id"] == str(redemption.vale_id)
    assert response.json()["usuario_cliente"]["id"] == str(redemption.cliente_id)
    assert response.json()["usuario_cajero_socio"] is None
    assert response.json()["sucursal"] is None
    assert response.json()["negocio"]["id"] == str(business.id)
    service.assert_awaited_once_with(
        session,
        redemption.id,
        principal.id,
        principal.role,
        principal.sucursal_id,
    )


@pytest.mark.parametrize("role", [Role.SUPERADMIN, Role.OWNER, Role.ADMIN])
def test_get_by_id_audit_permite_roles_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, session = route_context
    principal.role = role
    redemption = _redemption()
    voucher = _voucher(redemption)
    business = _business(voucher)
    detail = CanjeDetailResponseAudit(
        canje=redemption,
        usuario_cliente=_user(redemption.cliente_id),
        usuario_cajero_socio=None,
        vale=voucher,
        sucursal=None,
        negocio=business,
    )

    with patch.object(
        CanjeService,
        "get_audit",
        new=AsyncMock(return_value=detail),
    ) as service:
        response = client.get(f"/canjes/{redemption.id}/audit")

    assert response.status_code == 200
    assert response.json()["canje"]["id"] == str(redemption.id)
    service.assert_awaited_once_with(
        session,
        redemption.id,
        principal.id,
        principal.role,
        principal.sucursal_id,
    )


@pytest.mark.parametrize("role", [Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_get_by_id_audit_rechaza_roles_no_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, _ = route_context
    principal.role = role

    with patch.object(CanjeService, "get_audit", new=AsyncMock()) as service:
        response = client.get(f"/canjes/{uuid4()}/audit")

    assert response.status_code == 403
    service.assert_not_awaited()


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


@pytest.mark.parametrize(
    "role",
    [Role.SUPERADMIN, Role.OWNER, Role.ADMIN, Role.CAJERO],
)
def test_expire_permite_roles_autorizados_y_delega_actor(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, session = route_context
    principal.role = role
    with patch.object(
        CanjeService,
        "expire_pending",
        new=AsyncMock(return_value=CanjeExpireResponse(expired_count=3)),
    ) as service:
        response = client.post("/canjes/expire")

    assert response.status_code == 200
    assert response.json() == {"expired_count": 3}
    service.assert_awaited_once_with(session, actor_id=principal.id)


@pytest.mark.parametrize("role", [Role.CLIENTE, Role.SOCIO])
def test_expire_rechaza_roles_no_autorizados(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, _ = route_context
    principal.role = role

    with patch.object(CanjeService, "expire_pending", new=AsyncMock()) as service:
        response = client.post("/canjes/expire")

    assert response.status_code == 403
    service.assert_not_awaited()


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
        principal.sucursal_id,
    )
