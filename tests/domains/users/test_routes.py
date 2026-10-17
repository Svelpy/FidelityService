from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.users.models import User
from app.domains.users.routes import router
from app.domains.users.schemas import (
    UserDetailResponseAudit,
    UserMeResponse,
    UserResponse,
)
from app.domains.users.services import UserService
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Genero, Role
from app.shared.schemas.pagination import PaginatedResponse


def _user(**overrides: object) -> User:
    values: dict[str, object] = {
        "nombre": "Ana",
        "ci": "12345678",
        "telefono": "71234567",
        "role": Role.CLIENTE,
        "genero": Genero.F,
        "puntos": 0,
        "password_hash": "hash",
        "avatar_url": None,
        "sucursal_id": None,
    }
    values.update(overrides)
    return User(**values)


@pytest.fixture
def route_context() -> tuple[TestClient, CurrentUser, MagicMock, MagicMock]:
    app = FastAPI()
    register_exception_handlers(app, get_settings())
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
        yield client, current_user, db_session, settings


def test_get_me_delega_consulta_compuesta(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, _ = route_context
    user = _user(id=current_user.id)
    result = UserMeResponse(user=user, sucursal=None, negocio=None)

    with patch.object(
        UserService,
        "get_me",
        new=AsyncMock(return_value=result),
    ) as service:
        response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)
    assert response.json()["sucursal"] is None
    assert response.json()["negocio"] is None
    service.assert_awaited_once_with(db_session, current_user.id)


def test_update_me_reutiliza_update(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, _ = route_context
    user = _user(id=current_user.id, apellidos=None)

    with patch.object(
        UserService,
        "update",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.patch("/users/me", json={"apellidos": None})

    assert response.status_code == 200
    args = service.await_args
    assert args.args[:2] == (db_session, current_user.id)
    assert args.args[2].model_dump(exclude_unset=True) == {"apellidos": None}
    assert args.args[3] == current_user.id


def test_upload_my_avatar_acepta_multipart(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, settings = route_context
    user = _user(id=current_user.id)

    with patch.object(
        UserService,
        "upload_avatar",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.post(
            "/users/me/avatar",
            files={"file": ("avatar.png", b"png", "image/png")},
        )

    assert response.status_code == 200
    args = service.await_args
    assert args.args[:2] == (db_session, current_user.id)
    assert args.args[2].filename == "avatar.png"
    assert args.kwargs == {"actor_id": current_user.id, "settings": settings}


def test_delete_my_avatar_delega_service(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, _ = route_context
    user = _user(id=current_user.id)

    with patch.object(
        UserService,
        "delete_avatar",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.delete("/users/me/avatar")

    assert response.status_code == 200
    service.assert_awaited_once_with(
        db_session,
        current_user.id,
        actor_id=current_user.id,
    )


@pytest.mark.parametrize(
    "actor_role",
    [Role.SUPERADMIN, Role.OWNER, Role.ADMIN],
)
def test_list_users_permite_roles_autorizados_y_devuelve_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, db_session, _ = route_context
    current_user.role = actor_role
    user = _user()
    page = PaginatedResponse[UserResponse](
        total=1,
        page=1,
        per_page=10,
        total_pages=1,
        data=[user],
    )

    with patch.object(
        UserService,
        "list",
        new=AsyncMock(return_value=page),
    ) as service:
        sucursal_id = uuid4()
        response = client.get(
            f"/users/?page=1&per_page=10&sucursal_id={sucursal_id}&role=CAJERO"
        )

    assert response.status_code == 200
    service.assert_awaited_once_with(
        db_session,
        page=1,
        per_page=10,
        sucursal_id=sucursal_id,
        role=Role.CAJERO,
    )


@pytest.mark.parametrize("actor_role", [Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_list_users_rechaza_roles_no_autorizados(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, _, _ = route_context
    current_user.role = actor_role

    with patch.object(UserService, "list", new=AsyncMock()) as service:
        response = client.get("/users/")

    assert response.status_code == 403
    service.assert_not_awaited()


@pytest.mark.parametrize("actor_role", [Role.SUPERADMIN, Role.OWNER, Role.ADMIN])
def test_reset_password_permite_roles_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, db_session, _ = route_context
    current_user.role = actor_role
    user = _user()

    with patch.object(
        UserService,
        "reset_password",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.patch(
            f"/users/{user.id}/password",
            json={"new_password": "ClaveNueva123"},
        )

    assert response.status_code == 200
    args = service.await_args.args
    assert args[:2] == (db_session, user.id)
    assert args[2].new_password == "ClaveNueva123"
    assert args[3:] == (current_user.id, actor_role)


@pytest.mark.parametrize("actor_role", [Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_reset_password_rechaza_roles_no_administrativos(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, _, _ = route_context
    current_user.role = actor_role

    with patch.object(UserService, "reset_password", new=AsyncMock()) as service:
        response = client.patch(
            f"/users/{uuid4()}/password",
            json={"new_password": "ClaveNueva123"},
        )

    assert response.status_code == 403
    service.assert_not_awaited()


def test_create_admin_sin_sucursal_devuelve_201(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, _ = route_context
    user = _user(role=Role.ADMIN)

    with patch.object(
        UserService,
        "create",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.post(
            "/users/",
            json={
                "ci": user.ci,
                "telefono": user.telefono,
                "nombre": user.nombre,
                "genero": user.genero.value,
                "role": Role.ADMIN.value,
            },
        )

    assert response.status_code == 201
    args = service.await_args
    assert args.args[0] is db_session
    assert args.kwargs == {
        "actor_id": current_user.id,
        "actor_role": current_user.role,
    }


def test_get_update_delete_usuario_delegan_servicio(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, current_user, db_session, _ = route_context
    user = _user()

    detail = UserDetailResponseAudit(user=user, sucursal=None, negocio=None)
    with patch.object(
        UserService,
        "get_detail",
        new=AsyncMock(return_value=detail),
    ) as get_detail:
        response = client.get(f"/users/{user.id}")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)
    assert response.json()["sucursal"] is None
    assert response.json()["negocio"] is None
    get_detail.assert_awaited_once_with(db_session, user.id)

    with patch.object(
        UserService,
        "update",
        new=AsyncMock(return_value=user),
    ) as update:
        assert client.patch(f"/users/{user.id}", json={"email": None}).status_code == 200
        args = update.await_args.args
        assert args[:2] == (db_session, user.id)
        assert args[2].model_dump(exclude_unset=True) == {
            "email": None
        }
        assert args[3:] == (current_user.id, current_user.role)

    with patch.object(UserService, "delete", new=AsyncMock()) as delete:
        assert client.delete(f"/users/{user.id}").status_code == 204
        delete.assert_awaited_once_with(
            db_session,
            user.id,
            current_user.id,
            current_user.role,
        )


def test_get_user_by_ci_delega_consulta_administrativa(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, _, db_session, _ = route_context
    user = _user()

    with patch.object(
        UserService,
        "get_by_ci",
        new=AsyncMock(return_value=user),
    ) as service:
        response = client.get(f"/users/ci/{user.ci}")

    assert response.status_code == 200
    assert response.json()["ci"] == user.ci
    assert "user" not in response.json()
    assert "sucursal" not in response.json()
    assert "negocio" not in response.json()
    service.assert_awaited_once_with(db_session, user.ci)


def test_get_user_by_ci_valida_formato(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, _, _, _ = route_context

    assert client.get("/users/ci/ABC").status_code == 422


def test_list_users_valida_paginacion(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
) -> None:
    client, _, _, _ = route_context

    assert client.get("/users/?page=0").status_code == 422
    assert client.get("/users/?role=INVALIDO").status_code == 422
    assert client.get("/users/?sucursal_id=invalido").status_code == 422
