from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.domains.negocio.models import Negocio
from app.domains.negocio.schemas import NegocioCreate, NegocioUpdate
from app.domains.negocio.services import NegocioService
from app.domains.sucursal.models import Sucursal
from app.integrations.cloudinary import CloudinaryService
from app.shared.enums import TipoNegocio
from app.shared.errors.exceptions import AppException


def _negocio(**overrides: object) -> Negocio:
    values: dict[str, object] = {
        "nombre": "Café Central",
        "tipo": TipoNegocio.SOCIO,
        "descripcion": "Cafetería artesanal.",
        "telefono": "71234567",
        "image_url": None,
    }
    values.update(overrides)
    return Negocio(**values)


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_get_rechaza_negocio_inexistente() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await NegocioService.get(session, uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_devuelve_paginacion() -> None:
    negocio = _negocio()
    sucursal = Sucursal(nombre="Central", negocio_id=negocio.id)
    result = MagicMock()
    result.all.return_value = [(1, negocio, sucursal)]
    session = _session()
    session.execute.return_value = result

    page = await NegocioService.list(
        session,
        page=1,
        per_page=10,
        tipo=TipoNegocio.SOCIO,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert page.data[0].negocio.id == negocio.id
    assert page.data[0].negocio.tipo is TipoNegocio.SOCIO
    assert page.data[0].sucursales[0].id == sucursal.id
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_con_pagina_vacia_conserva_el_total() -> None:
    result = MagicMock()
    result.all.return_value = [(2, None, None)]
    session = _session()
    session.execute.return_value = result

    page = await NegocioService.list(session, page=2, per_page=2)

    assert page.total == 2
    assert page.total_pages == 1
    assert page.data == []
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_with_sucursales_devuelve_detalle_auditado() -> None:
    negocio = _negocio()
    sucursal = Sucursal(nombre="Central", negocio_id=negocio.id)
    result = MagicMock()
    result.all.return_value = [(negocio, sucursal)]
    session = _session()
    session.execute.return_value = result

    detail = await NegocioService.get_with_sucursales(
        session,
        negocio.id,
    )

    assert detail.negocio.id == negocio.id
    assert detail.sucursales[0].id == sucursal.id
    assert detail.negocio.is_deleted is False
    assert detail.sucursales[0].is_deleted is False
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_with_sucursales_incluye_negocio_sin_sucursales() -> None:
    negocio = _negocio()
    result = MagicMock()
    result.all.return_value = [(negocio, None)]
    session = _session()
    session.execute.return_value = result

    detail = await NegocioService.get_with_sucursales(session, negocio.id)

    assert detail.negocio.id == negocio.id
    assert detail.sucursales == []
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_asigna_auditoria() -> None:
    session = _session()
    session.execute.return_value = _scalar_result(None)
    actor_id = uuid4()

    negocio = await NegocioService.create(
        session,
        NegocioCreate(nombre="Café Central", tipo=TipoNegocio.SOCIO),
        actor_id,
    )

    assert negocio.created_by == actor_id
    assert negocio.updated_by == actor_id
    assert negocio.image_url is None
    session.add.assert_called_once_with(negocio)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(negocio)


@pytest.mark.asyncio
async def test_validate_unique_name_rechaza_nombre_activo_duplicado() -> None:
    session = _session()
    session.execute.return_value = _scalar_result(uuid4())

    with pytest.raises(AppException) as error:
        await NegocioService._validate_unique_name(session, "café central")

    assert error.value.status_code == 409
    assert error.value.details == {
        "nombre": "El nombre ya está registrado por un negocio activo."
    }


@pytest.mark.asyncio
async def test_validate_single_active_main_rechaza_segundo_main() -> None:
    session = _session()
    session.execute.return_value = _scalar_result(uuid4())

    with pytest.raises(AppException) as error:
        await NegocioService._validate_single_active_main(session)

    assert error.value.status_code == 409
    assert error.value.details == {
        "tipo": "Solo puede existir un negocio activo de tipo MAIN."
    }


@pytest.mark.asyncio
async def test_create_main_aplica_ambas_validaciones() -> None:
    session = _session()
    actor_id = uuid4()

    with (
        patch.object(
            NegocioService,
            "_validate_unique_name",
            new=AsyncMock(),
        ) as validate_name,
        patch.object(
            NegocioService,
            "_validate_single_active_main",
            new=AsyncMock(),
        ) as validate_main,
        patch.object(NegocioService, "_commit", new=AsyncMock()),
    ):
        await NegocioService.create(
            session,
            NegocioCreate(nombre="Farmacia Tupa", tipo=TipoNegocio.MAIN),
            actor_id,
        )

    validate_name.assert_awaited_once_with(session, "Farmacia Tupa")
    validate_main.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_update_conserva_null_explicito() -> None:
    negocio = _negocio(descripcion="Anterior", telefono="71234567")
    actor_id = uuid4()

    with (
        patch.object(NegocioService, "get", new=AsyncMock(return_value=negocio)),
        patch.object(NegocioService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await NegocioService.update(
            MagicMock(),
            negocio.id,
            NegocioUpdate(descripcion=None, telefono=None),
            actor_id,
        )

    assert updated.descripcion is None
    assert updated.telefono is None
    assert updated.updated_by == actor_id
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_aplica_soft_delete() -> None:
    negocio = _negocio()
    actor_id = uuid4()

    with (
        patch.object(NegocioService, "get", new=AsyncMock(return_value=negocio)),
        patch.object(NegocioService, "_commit", new=AsyncMock()) as commit,
    ):
        deleted = await NegocioService.delete(
            MagicMock(),
            negocio.id,
            actor_id,
        )

    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    assert deleted.deleted_by == actor_id
    assert deleted.updated_at == deleted.deleted_at
    assert deleted.updated_by == actor_id
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_image_reemplaza_y_limpia_imagen_anterior() -> None:
    previous_url = "https://res.cloudinary.com/demo/image/upload/old.jpg"
    new_url = "https://res.cloudinary.com/demo/image/upload/new.jpg"
    negocio = _negocio(image_url=previous_url)
    actor_id = uuid4()
    file = MagicMock(spec=UploadFile)
    settings = MagicMock(spec=Settings)
    session = _session()

    with (
        patch.object(NegocioService, "get", new=AsyncMock(return_value=negocio)),
        patch.object(
            NegocioService,
            "_commit_transaction",
            new=AsyncMock(),
        ) as commit,
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
        updated = await NegocioService.upload_image(
            session,
            negocio.id,
            file,
            actor_id,
            settings,
        )

    assert updated.image_url == new_url
    assert updated.updated_by == actor_id
    upload.assert_awaited_once_with(
        file,
        folder=f"negocios/{negocio.id}",
        settings=settings,
    )
    commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(negocio)
    safe_delete.assert_awaited_once_with(previous_url)


@pytest.mark.asyncio
async def test_upload_image_elimina_nueva_imagen_si_falla_commit() -> None:
    new_url = "https://res.cloudinary.com/demo/image/upload/new.jpg"
    negocio = _negocio()

    with (
        patch.object(NegocioService, "get", new=AsyncMock(return_value=negocio)),
        patch.object(
            NegocioService,
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
            await NegocioService.upload_image(
                MagicMock(),
                negocio.id,
                MagicMock(spec=UploadFile),
                uuid4(),
                MagicMock(spec=Settings),
            )

    safe_delete.assert_awaited_once_with(new_url)


@pytest.mark.asyncio
async def test_delete_image_limpia_url_y_cloudinary() -> None:
    image_url = "https://res.cloudinary.com/demo/image/upload/logo.jpg"
    negocio = _negocio(image_url=image_url)
    actor_id = uuid4()

    with (
        patch.object(NegocioService, "get", new=AsyncMock(return_value=negocio)),
        patch.object(NegocioService, "_commit", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService,
            "safe_delete_image",
            new=AsyncMock(return_value=True),
        ) as safe_delete,
    ):
        updated = await NegocioService.delete_image(
            MagicMock(),
            negocio.id,
            actor_id,
        )

    assert updated.image_url is None
    assert updated.updated_by == actor_id
    commit.assert_awaited_once()
    safe_delete.assert_awaited_once_with(image_url)
