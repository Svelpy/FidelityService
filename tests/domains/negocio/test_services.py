from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.domains.negocio.models import Negocio
from app.domains.negocio.schemas import NegocioCreate, NegocioUpdate
from app.domains.negocio.services import NegocioService
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
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [negocio]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await NegocioService.list(
        session,
        page=1,
        per_page=10,
        tipo=TipoNegocio.SOCIO,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert page.data[0].id == negocio.id
    assert page.data[0].tipo is TipoNegocio.SOCIO


@pytest.mark.asyncio
async def test_create_asigna_auditoria() -> None:
    session = _session()
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
