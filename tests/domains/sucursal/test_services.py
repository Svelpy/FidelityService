from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.negocio.models import Negocio
from app.domains.negocio.services import NegocioService
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.schemas import SucursalCreate, SucursalUpdate
from app.domains.sucursal.services import SucursalService
from app.shared.enums import TipoNegocio
from app.shared.errors.exceptions import AppException


def _sucursal(**overrides: object) -> Sucursal:
    values: dict[str, object] = {
        "nombre": "Sucursal Equipetrol",
        "negocio_id": uuid4(),
        "direccion": "Av. San Martín 123",
        "url_ubicacion": "https://maps.google.com/?q=-17.77,-63.20",
        "telefono": "71234567",
    }
    values.update(overrides)
    return Sucursal(**values)


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_rechaza_sucursal_inexistente() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await SucursalService.get(session, uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_devuelve_paginacion_filtrada_por_negocio() -> None:
    negocio_id = uuid4()
    sucursal = _sucursal(negocio_id=negocio_id)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [sucursal]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await SucursalService.list(
        session,
        page=1,
        per_page=10,
        negocio_id=negocio_id,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert page.data[0].negocio_id == negocio_id


@pytest.mark.asyncio
async def test_create_valida_negocio_y_asigna_auditoria() -> None:
    session = _session()
    actor_id = uuid4()
    negocio_id = uuid4()
    negocio = Negocio(nombre="Café Central", tipo=TipoNegocio.SOCIO)

    with patch.object(
        NegocioService,
        "get",
        new=AsyncMock(return_value=negocio),
    ) as get_negocio:
        sucursal = await SucursalService.create(
            session,
            SucursalCreate(nombre="Sucursal Equipetrol", negocio_id=negocio_id),
            actor_id,
        )

    get_negocio.assert_awaited_once_with(session, negocio_id)
    assert sucursal.created_by == actor_id
    assert sucursal.updated_by == actor_id
    session.add.assert_called_once_with(sucursal)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(sucursal)


@pytest.mark.asyncio
async def test_update_conserva_null_explicito() -> None:
    sucursal = _sucursal()
    actor_id = uuid4()

    with (
        patch.object(SucursalService, "get", new=AsyncMock(return_value=sucursal)),
        patch.object(SucursalService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await SucursalService.update(
            MagicMock(),
            sucursal.id,
            SucursalUpdate(direccion=None, url_ubicacion=None, telefono=None),
            actor_id,
        )

    assert updated.direccion is None
    assert updated.url_ubicacion is None
    assert updated.telefono is None
    assert updated.updated_by == actor_id
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_valida_nuevo_negocio() -> None:
    sucursal = _sucursal()
    nuevo_negocio_id = uuid4()

    with (
        patch.object(SucursalService, "get", new=AsyncMock(return_value=sucursal)),
        patch.object(NegocioService, "get", new=AsyncMock()) as get_negocio,
        patch.object(SucursalService, "_commit", new=AsyncMock()),
    ):
        updated = await SucursalService.update(
            MagicMock(),
            sucursal.id,
            SucursalUpdate(negocio_id=nuevo_negocio_id),
            uuid4(),
        )

    assert updated.negocio_id == nuevo_negocio_id
    get_negocio.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_aplica_soft_delete() -> None:
    sucursal = _sucursal()
    actor_id = uuid4()

    with (
        patch.object(SucursalService, "get", new=AsyncMock(return_value=sucursal)),
        patch.object(
            SucursalService,
            "_validate_without_linked_users",
            new=AsyncMock(),
        ) as validate_without_linked_users,
        patch.object(SucursalService, "_commit", new=AsyncMock()) as commit,
    ):
        deleted = await SucursalService.delete(
            MagicMock(),
            sucursal.id,
            actor_id,
        )

    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    assert deleted.deleted_by == actor_id
    assert deleted.updated_at == deleted.deleted_at
    assert deleted.updated_by == actor_id
    validate_without_linked_users.assert_awaited_once_with(ANY, sucursal.id)
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_rechaza_sucursal_con_usuarios_asociados() -> None:
    sucursal = _sucursal()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    session = _session()
    session.execute.return_value = result

    with patch.object(
        SucursalService,
        "get",
        new=AsyncMock(return_value=sucursal),
    ):
        with pytest.raises(AppException) as error:
            await SucursalService.delete(session, sucursal.id, uuid4())

    assert error.value.status_code == 409
    assert error.value.details == {
        "sucursal_id": "La sucursal tiene usuarios activos o históricos asociados."
    }
    assert sucursal.is_deleted is False
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_commit_traduce_integrity_error_y_hace_rollback() -> None:
    session = _session()
    session.commit.side_effect = IntegrityError("statement", {}, Exception("fk"))

    with pytest.raises(AppException) as error:
        await SucursalService._commit(session, _sucursal())

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
