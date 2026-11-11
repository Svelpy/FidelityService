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
from app.domains.operacion.models import Operacion
from app.domains.operacion.routes import router
from app.domains.operacion.schemas import (
    OperacionDetailResponse,
    OperacionListResponse,
    OperacionResponseAudit,
)
from app.domains.operacion.services import OperacionService
from app.shared.enums import Role
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


def _operation() -> Operacion:
    return Operacion(
        receptor_id=uuid4(),
        emisor_id=uuid4(),
        total_compra=Decimal("100.00"),
        total_puntos=10,
        config_punto_id=uuid4(),
        sucursal_id=uuid4(),
    )


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock]:
    app = FastAPI()
    app.include_router(router)
    current_user = CurrentUser(
        id=uuid4(),
        role=Role.CAJERO,
        sucursal_id=uuid4(),
    )
    db_session = MagicMock(spec=AsyncSession)

    async def principal() -> CurrentUser:
        return current_user

    async def database() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = principal
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, current_user, db_session


def test_create_delega_contexto_del_emisor(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    operation = _operation()
    with patch.object(
        OperacionService,
        "create",
        new=AsyncMock(return_value=operation),
    ) as service:
        response = client.post(
            "/operaciones/",
            json={
                "receptor_id": str(operation.receptor_id),
                "receptor_data": {
                    "ci": "12345678",
                    "telefono": "71234567",
                    "nombre": "Ana",
                    "genero": "F",
                },
                "total_compra": "100.00",
            },
        )

    assert response.status_code == 201
    service.assert_awaited_once()
    assert service.await_args.args[0] is session
    assert service.await_args.args[2:] == (principal.id, principal.sucursal_id)


def test_get_delega_alcance_del_principal(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    detail = OperacionDetailResponse.model_validate(
        OperacionDetailResponse.model_json_schema()["example"]
    )
    with patch.object(
        OperacionService,
        "get",
        new=AsyncMock(return_value=detail),
    ) as service:
        response = client.get(f"/operaciones/{detail.operacion.id}")

    assert response.status_code == 200
    assert response.json()["negocio"]["id"] == str(detail.negocio.id)
    service.assert_awaited_once_with(
        session,
        detail.operacion.id,
        principal.id,
        principal.role,
    )


def test_get_audit_delega_alcance_del_principal(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.SUPERADMIN
    operation = OperacionResponseAudit.model_validate(
        OperacionResponseAudit.model_json_schema()["example"]
    )
    with patch.object(
        OperacionService,
        "get_audit",
        new=AsyncMock(return_value=operation),
    ) as service:
        response = client.get(f"/operaciones/{operation.id}/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(operation.id)
    assert body["deleted_at"] is not None
    assert "receptor" not in body
    service.assert_awaited_once_with(
        session,
        operation.id,
        principal.id,
        principal.role,
    )


def test_list_delega_filtros_opcionales(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    operation = _operation()
    item = OperacionListResponse.model_validate(
        OperacionListResponse.model_json_schema()["example"]
    )
    page = PaginatedResponse[OperacionListResponse](
        total=1,
        page=1,
        per_page=10,
        total_pages=1,
        data=[item],
    )

    with patch.object(
        OperacionService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        response = client.get(
            "/operaciones/",
            params={
                "page": 1,
                "per_page": 10,
                "emisor_id": str(operation.emisor_id),
                "receptor_id": str(operation.receptor_id),
                "sucursal_id": str(operation.sucursal_id),
            },
        )

    assert response.status_code == 200
    body = response.json()["data"][0]
    assert body["operacion"]["id"] == str(item.operacion.id)
    assert body["receptor"]["id"] == str(item.receptor.id)
    assert body["emisor"]["role"] == "CAJERO"
    assert body["sucursal"]["nombre"] == item.sucursal.nombre
    service.assert_awaited_once_with(
        session,
        principal.id,
        principal.role,
        page=1,
        per_page=10,
        emisor_id=operation.emisor_id,
        receptor_id=operation.receptor_id,
        sucursal_id=operation.sucursal_id,
        anulada=None,
    )


def test_list_valida_ids_de_filtro(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, _, _ = route_context

    assert client.get("/operaciones/?emisor_id=invalido").status_code == 422
    assert client.get("/operaciones/?receptor_id=invalido").status_code == 422
    assert client.get("/operaciones/?sucursal_id=invalido").status_code == 422


def test_cancel_delega_motivo_y_principal(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, session = route_context
    principal.role = Role.ADMIN
    operation = _operation()
    with patch.object(
        OperacionService,
        "cancel",
        new=AsyncMock(return_value=operation),
    ) as service:
        response = client.post(
            f"/operaciones/{operation.id}/cancel",
            json={"motivo": "  Monto mal digitado  "},
        )

    assert response.status_code == 200
    service.assert_awaited_once()
    args = service.await_args.args
    assert args[0] is session
    assert args[1] == operation.id
    assert args[2].motivo == "Monto mal digitado"
    assert args[3:] == (principal.id, principal.role)


@pytest.mark.parametrize("role", [Role.CAJERO, Role.SUPERADMIN, Role.CLIENTE, Role.SOCIO])
def test_cancel_rechaza_roles_sin_permiso_de_anular(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
    role: Role,
) -> None:
    client, principal, _ = route_context
    principal.role = role
    with (
        patch.object(OperacionService, "cancel", new=AsyncMock()) as service,
        pytest.raises(AppException) as error,
    ):
        client.post(
            f"/operaciones/{uuid4()}/cancel",
            json={"motivo": "Monto mal digitado"},
        )

    assert error.value.status_code == 403
    service.assert_not_awaited()


def test_cancel_requiere_motivo(
    route_context: tuple[TestClient, CurrentUser, MagicMock],
) -> None:
    client, principal, _ = route_context
    principal.role = Role.OWNER

    assert client.post(f"/operaciones/{uuid4()}/cancel", json={}).status_code == 422
