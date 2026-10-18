from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.domains.auth.services import AuthService
from app.domains.negocio.models import Negocio
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.users.schemas import (
    AdminResetPassword,
    PasswordSelfUpdate,
    UserCreate,
    UserRegistrationData,
    UserSelfUpdate,
    UserUpdate,
)
from app.domains.users.services import UserService
from app.integrations.cloudinary import CloudinaryService
from app.shared.enums import Genero, Role, TipoNegocio
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


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


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.parametrize("role", [Role.CAJERO, Role.SOCIO])
def test_roles_operativos_requieren_sucursal(role: Role) -> None:
    with pytest.raises(AppException) as error:
        UserService._validate_required_sucursal(role, None)

    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "role",
    [Role.CLIENTE, Role.ADMIN, Role.OWNER, Role.SUPERADMIN],
)
def test_roles_globales_no_requieren_sucursal(role: Role) -> None:
    UserService._validate_required_sucursal(role, None)


def test_admin_no_puede_administrar_un_rol_del_mismo_nivel() -> None:
    with pytest.raises(AppException) as error:
        UserService._validate_can_manage_role(Role.ADMIN, Role.ADMIN)

    assert error.value.status_code == 403
    assert error.value.code == ErrorCode.PERMISSION_DENIED


def test_superadmin_puede_administrar_owner() -> None:
    UserService._validate_can_manage_role(Role.SUPERADMIN, Role.OWNER)


@pytest.mark.parametrize("target_role", [Role.ADMIN, Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_owner_puede_administrar_roles_inferiores(target_role: Role) -> None:
    UserService._validate_can_manage_role(Role.OWNER, target_role)


@pytest.mark.parametrize("target_role", [Role.SUPERADMIN, Role.OWNER])
def test_owner_no_puede_administrar_su_nivel_o_superior(
    target_role: Role,
) -> None:
    with pytest.raises(AppException) as error:
        UserService._validate_can_manage_role(Role.OWNER, target_role)

    assert error.value.status_code == 403
    assert error.value.code == ErrorCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_commit_traduce_constraint_de_socio_y_revierte_transaccion() -> None:
    original_error = MagicMock()
    original_error.constraint_name = "ck_usuario_socio_sucursal_compatible"
    session = _session()
    session.commit.side_effect = IntegrityError(None, None, original_error)

    with pytest.raises(AppException) as error:
        await UserService._commit_transaction(session)

    assert error.value.status_code == 422
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert error.value.details == {
        "sucursal_id": "La sucursal debe pertenecer a un negocio de tipo SOCIO."
    }
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_rechaza_usuario_inexistente() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await UserService.get(session, uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_get_me_devuelve_usuario_sucursal_y_negocio_en_una_consulta() -> None:
    negocio = Negocio(nombre="Cafe Central", tipo=TipoNegocio.SOCIO)
    sucursal = Sucursal(
        nombre="Sucursal Centro",
        negocio_id=negocio.id,
    )
    user = _user(sucursal_id=sucursal.id)
    result = MagicMock()
    result.one_or_none.return_value = (user, sucursal, negocio)
    session = _session()
    session.execute.return_value = result

    response = await UserService.get_me(session, user.id)

    assert response.user.id == user.id
    assert response.sucursal is not None
    assert response.sucursal.id == sucursal.id
    assert response.negocio is not None
    assert response.negocio.id == negocio.id
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_me_admite_usuario_sin_sucursal() -> None:
    user = _user(sucursal_id=None)
    result = MagicMock()
    result.one_or_none.return_value = (user, None, None)
    session = _session()
    session.execute.return_value = result

    response = await UserService.get_me(session, user.id)

    assert response.user.id == user.id
    assert response.sucursal is None
    assert response.negocio is None


@pytest.mark.asyncio
async def test_get_detail_devuelve_respuestas_con_auditoria() -> None:
    negocio = Negocio(nombre="Cafe Central", tipo=TipoNegocio.SOCIO)
    sucursal = Sucursal(
        nombre="Sucursal Centro",
        negocio_id=negocio.id,
    )
    user = _user(sucursal_id=sucursal.id)
    result = MagicMock()
    result.one_or_none.return_value = (user, sucursal, negocio)
    session = _session()
    session.execute.return_value = result

    response = await UserService.get_detail(session, user.id)

    assert response.user.created_at == user.created_at
    assert response.sucursal is not None
    assert response.sucursal.created_at == sucursal.created_at
    assert response.negocio is not None
    assert response.negocio.created_at == negocio.created_at
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_ci_devuelve_solo_usuario() -> None:
    user = _user(ci="12345678")
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session = _session()
    session.execute.return_value = result

    response = await UserService.get_by_ci(session, user.ci)

    assert response.id == user.id
    statement = session.execute.await_args.args[0]
    assert user.ci in statement.compile().params.values()


@pytest.mark.asyncio
async def test_get_me_rechaza_usuario_inexistente() -> None:
    result = MagicMock()
    result.one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await UserService.get_me(session, uuid4())

    assert error.value.status_code == 404
    assert error.value.code == ErrorCode.RESOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_list_devuelve_paginacion() -> None:
    sucursal_id = uuid4()
    user = _user(role=Role.CAJERO, sucursal_id=sucursal_id)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [user]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await UserService.list(
        session,
        page=1,
        per_page=10,
        sucursal_id=sucursal_id,
        role=Role.CAJERO,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert page.data[0].id == user.id
    count_statement = session.execute.await_args_list[0].args[0]
    rows_statement = session.execute.await_args_list[1].args[0]
    for statement in (count_statement, rows_statement):
        parameters = statement.compile().params.values()
        assert sucursal_id in parameters
        assert Role.CAJERO in parameters
    assert "usuario.puntos DESC" not in str(rows_statement.compile())


@pytest.mark.asyncio
async def test_list_ordena_por_puntos_descendente_cuando_se_solicita() -> None:
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    await UserService.list(session, order_by_points=True)

    rows_statement = session.execute.await_args_list[1].args[0]
    compiled_statement = str(rows_statement.compile())
    assert "usuario.puntos DESC" in compiled_statement
    assert compiled_statement.index("usuario.puntos DESC") < compiled_statement.index(
        "usuario.created_at DESC"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page", "per_page"),
    [(0, 20), (1, 0), (1, 101)],
)
async def test_list_rechaza_paginacion_invalida(page: int, per_page: int) -> None:
    with pytest.raises(AppException) as error:
        await UserService.list(MagicMock(), page=page, per_page=per_page)

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_validaciones_de_unicidad_rechazan_ci_y_email_duplicados() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as ci_error:
        await UserService._validate_unique_ci(session, "12345678")
    with pytest.raises(AppException) as email_error:
        await UserService._validate_unique_email(session, "ana@example.com")

    assert ci_error.value.details == {
        "ci": "La cédula de identidad ya está registrada."
    }
    assert email_error.value.details == {
        "email": "El email ya está registrado."
    }


@pytest.mark.asyncio
async def test_create_admin_sin_sucursal_asigna_hash_y_auditoria() -> None:
    session = _session()
    actor_id = uuid4()
    data = UserCreate(
        ci="12345678",
        telefono="71234567",
        nombre="Ana",
        genero=Genero.F,
        role=Role.ADMIN,
        sucursal_id=None,
    )

    with (
        patch.object(UserService, "_validate_unique_ci", new=AsyncMock()),
        patch.object(UserService, "_validate_unique_email", new=AsyncMock()),
        patch.object(UserService, "_validate_sucursal", new=AsyncMock()),
        patch("app.domains.users.services.hash_password", return_value="secure-hash") as hasher,
    ):
        user = await UserService.create(
            session,
            data,
            actor_id,
            Role.SUPERADMIN,
        )

    assert user.role is Role.ADMIN
    assert user.sucursal_id is None
    assert user.password_hash == "secure-hash"
    assert user.created_by == actor_id
    assert user.updated_by == actor_id
    hasher.assert_called_once_with("71234567")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_crea_cliente_sin_sucursal() -> None:
    session = _session()
    data = UserRegistrationData(
        ci="87654321",
        telefono="72123456",
        nombre="Luis",
        genero=Genero.M,
    )

    with (
        patch.object(UserService, "_validate_unique_ci", new=AsyncMock()),
        patch.object(UserService, "_validate_unique_email", new=AsyncMock()),
        patch("app.domains.users.services.hash_password", return_value="secure-hash"),
    ):
        user = await UserService.register(session, data)

    assert user.role is Role.CLIENTE
    assert user.sucursal_id is None
    assert user.created_by == user.id
    assert user.updated_by == user.id


@pytest.mark.asyncio
async def test_register_sin_commit_permite_transaccion_externa() -> None:
    session = _session()
    data = UserRegistrationData(
        ci="87654321",
        telefono="72123456",
        nombre="Luis",
        genero=Genero.M,
    )

    with (
        patch.object(UserService, "_validate_unique_ci", new=AsyncMock()),
        patch.object(UserService, "_validate_unique_email", new=AsyncMock()),
        patch("app.domains.users.services.hash_password", return_value="secure-hash"),
    ):
        user = await UserService.register(session, data, commit=False)

    session.add.assert_called_once_with(user)
    assert user.role is Role.CLIENTE
    assert user.sucursal_id is None
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_update_conserva_null_explicito() -> None:
    user = _user(apellidos="Pérez", email="ana@example.com")

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(UserService, "_validate_unique_email", new=AsyncMock()),
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await UserService.update(
            MagicMock(),
            user.id,
            UserSelfUpdate(apellidos=None, email=None),
            user.id,
        )

    assert updated.apellidos is None
    assert updated.email is None
    assert updated.updated_by == user.id
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_update_valida_rol_y_sucursal_resultantes() -> None:
    user = _user()
    actor_id = uuid4()
    sucursal_id = uuid4()
    session = _session()
    data = UserUpdate(role=Role.SOCIO, sucursal_id=sucursal_id)

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(UserService, "_validate_sucursal", new=AsyncMock()) as validate,
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await UserService.update(
            session,
            user.id,
            data,
            actor_id,
            Role.SUPERADMIN,
        )

    assert updated.role is Role.SOCIO
    assert updated.sucursal_id == sucursal_id
    assert updated.updated_by == actor_id
    validate.assert_awaited_once_with(session, sucursal_id)
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_vacio_no_escribe_en_base_de_datos() -> None:
    user = _user()
    session = _session()

    with patch.object(
        UserService,
        "get",
        new=AsyncMock(return_value=user),
    ) as get_user:
        updated = await UserService.update(
            session,
            user.id,
            UserUpdate(),
            uuid4(),
            Role.ADMIN,
        )

    assert updated is user
    get_user.assert_awaited_once_with(session, user.id)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_revoca_sesiones_y_aplica_soft_delete() -> None:
    user = _user()
    actor_id = uuid4()

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(AuthService, "revoke_for_user", new=AsyncMock()) as revoke,
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
    ):
        deleted = await UserService.delete(
            MagicMock(),
            user.id,
            actor_id,
            Role.SUPERADMIN,
        )

    assert deleted.is_deleted is True
    assert deleted.deleted_by == actor_id
    revoke.assert_awaited_once()
    assert revoke.await_args.args[1:] == (user.id, "user_deleted")
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_password_rechaza_password_actual_incorrecta() -> None:
    user = _user()

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch("app.domains.users.services.verify_password", return_value=False),
    ):
        with pytest.raises(AppException) as error:
            await UserService.change_password(
                MagicMock(),
                user.id,
                PasswordSelfUpdate(
                    current_password="ClaveActual",
                    new_password="NuevaClave123",
                ),
                user.id,
            )

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_change_password_actualiza_hash_y_revoca_sesiones() -> None:
    user = _user()
    actor_id = uuid4()
    data = PasswordSelfUpdate(
        current_password="ClaveActual",
        new_password="NuevaClave123",
    )

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch("app.domains.users.services.verify_password", return_value=True),
        patch("app.domains.users.services.hash_password", return_value="new-hash"),
        patch.object(AuthService, "revoke_for_user", new=AsyncMock()) as revoke,
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await UserService.change_password(
            MagicMock(),
            user.id,
            data,
            actor_id,
        )

    assert updated.password_hash == "new-hash"
    assert updated.updated_by == actor_id
    assert revoke.await_args.args[1:] == (user.id, "password_changed")
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_actualiza_hash_y_revoca_sesiones() -> None:
    user = _user()
    actor_id = uuid4()

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch("app.domains.users.services.verify_password", return_value=False),
        patch("app.domains.users.services.hash_password", return_value="reset-hash"),
        patch.object(AuthService, "revoke_for_user", new=AsyncMock()) as revoke,
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await UserService.reset_password(
            MagicMock(),
            user.id,
            AdminResetPassword(new_password="ClaveNueva123"),
            actor_id,
            Role.SUPERADMIN,
        )

    assert updated.password_hash == "reset-hash"
    assert updated.updated_by == actor_id
    assert revoke.await_args.args[1:] == (user.id, "admin_password_reset")
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_avatar_reemplaza_imagen_anterior() -> None:
    previous_url = "https://res.cloudinary.com/demo/image/upload/old.jpg"
    new_url = "https://res.cloudinary.com/demo/image/upload/new.jpg"
    user = _user(avatar_url=previous_url)
    session = _session()
    file = MagicMock(spec=UploadFile)
    settings = MagicMock(spec=Settings)

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(UserService, "_commit_transaction", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService,
            "upload_image",
            new=AsyncMock(return_value={"url": new_url, "public_id": "new"}),
        ) as upload,
        patch.object(
            CloudinaryService,
            "safe_delete_image",
            new=AsyncMock(return_value=True),
        ) as safe_delete,
    ):
        updated = await UserService.upload_avatar(
            session,
            user.id,
            file,
            user.id,
            settings,
        )

    assert updated.avatar_url == new_url
    upload.assert_awaited_once_with(
        file,
        folder=f"users/{user.id}/avatar",
        settings=settings,
    )
    commit.assert_awaited_once_with(session)
    session.refresh.assert_awaited_once_with(user)
    safe_delete.assert_awaited_once_with(previous_url)


@pytest.mark.asyncio
async def test_upload_avatar_elimina_imagen_nueva_si_falla_commit() -> None:
    new_url = "https://res.cloudinary.com/demo/image/upload/new.jpg"
    user = _user()

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(
            UserService,
            "_commit_transaction",
            new=AsyncMock(side_effect=RuntimeError("database error")),
        ),
        patch.object(
            CloudinaryService,
            "upload_image",
            new=AsyncMock(return_value={"url": new_url, "public_id": "new"}),
        ),
        patch.object(
            CloudinaryService,
            "safe_delete_image",
            new=AsyncMock(return_value=True),
        ) as safe_delete,
    ):
        with pytest.raises(RuntimeError):
            await UserService.upload_avatar(
                MagicMock(),
                user.id,
                MagicMock(spec=UploadFile),
                user.id,
                MagicMock(spec=Settings),
            )

    safe_delete.assert_awaited_once_with(new_url)


@pytest.mark.asyncio
async def test_delete_avatar_limpia_url_y_cloudinary() -> None:
    avatar_url = "https://res.cloudinary.com/demo/image/upload/avatar.jpg"
    user = _user(avatar_url=avatar_url)

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService,
            "safe_delete_image",
            new=AsyncMock(return_value=True),
        ) as safe_delete,
    ):
        updated = await UserService.delete_avatar(
            MagicMock(),
            user.id,
            user.id,
        )

    assert updated.avatar_url is None
    commit.assert_awaited_once()
    safe_delete.assert_awaited_once_with(avatar_url)


@pytest.mark.asyncio
async def test_delete_avatar_sin_imagen_es_idempotente() -> None:
    user = _user(avatar_url=None)

    with (
        patch.object(UserService, "get", new=AsyncMock(return_value=user)),
        patch.object(UserService, "_commit", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService,
            "safe_delete_image",
            new=AsyncMock(),
        ) as safe_delete,
    ):
        updated = await UserService.delete_avatar(
            MagicMock(),
            user.id,
            user.id,
        )

    assert updated is user
    commit.assert_not_awaited()
    safe_delete.assert_not_awaited()
