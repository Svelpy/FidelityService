from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.domains.categoria.services import CategoriaService
from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.negocio.services import NegocioService
from app.domains.vale.models import Vale
from app.domains.vale.schemas import ValeCreate, ValeUpdate
from app.domains.vale.services import ValeService
from app.integrations.cloudinary import CloudinaryService
from app.shared.errors.exceptions import AppException


def _vale(**overrides: object) -> Vale:
    values: dict[str, object] = {
        "total_costo": Decimal("50.00"),
        "total_puntos": 450,
        "nombre": "Vale Bs 50",
        "descripcion": None,
        "image_url": None,
        "categoria_id": uuid4(),
        "negocio_id": uuid4(),
    }
    values.update(overrides)
    return Vale(**values)


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_suggest_points_redondea_hacia_arriba() -> None:
    config = ConfigPuntos(
        start_date="2026-01-01T00:00:00Z",
        factor_asignacion_puntos=Decimal("0.100000"),
        factor_costo_vale=Decimal("3.333333"),
    )
    with patch.object(
        ConfigPuntosService, "get_active", new=AsyncMock(return_value=config)
    ):
        response = await ValeService.suggest_points(MagicMock(), Decimal("10.00"))
    assert response.puntos_sugeridos == 34


@pytest.mark.asyncio
async def test_suggest_points_rechaza_resultado_fuera_de_integer() -> None:
    config = ConfigPuntos(
        start_date="2026-01-01T00:00:00Z",
        factor_asignacion_puntos=Decimal("1.000000"),
        factor_costo_vale=Decimal("999999999999.999999"),
    )
    with patch.object(
        ConfigPuntosService, "get_active", new=AsyncMock(return_value=config)
    ):
        with pytest.raises(AppException) as error:
            await ValeService.suggest_points(MagicMock(), Decimal("10.00"))
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_get_rechaza_vale_inexistente() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result
    with pytest.raises(AppException) as error:
        await ValeService.get(session, uuid4())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_devuelve_paginacion_filtrada() -> None:
    vale = _vale()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [vale]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]
    page = await ValeService.list(
        session,
        page=1,
        per_page=10,
        categoria_id=vale.categoria_id,
        negocio_id=vale.negocio_id,
    )
    assert page.total == 1
    assert page.data[0].id == vale.id


@pytest.mark.asyncio
async def test_create_valida_referencias_y_respeta_puntos_manuales() -> None:
    session = _session()
    actor_id = uuid4()
    data = ValeCreate(
        total_costo="50.00",
        total_puntos=450,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    with (
        patch.object(CategoriaService, "get", new=AsyncMock()) as category,
        patch.object(NegocioService, "get", new=AsyncMock()) as business,
    ):
        vale = await ValeService.create(session, data, actor_id)
    assert vale.total_puntos == 450
    assert vale.created_by == actor_id
    category.assert_awaited_once_with(session, data.categoria_id)
    business.assert_awaited_once_with(session, data.negocio_id)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_conserva_null_explicito() -> None:
    vale = _vale(descripcion="Texto")
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(ValeService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await ValeService.update(
            MagicMock(), vale.id, ValeUpdate(descripcion=None), uuid4()
        )
    assert updated.descripcion is None
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_valida_nuevas_referencias() -> None:
    vale = _vale()
    categoria_id = uuid4()
    negocio_id = uuid4()
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(CategoriaService, "get", new=AsyncMock()) as category,
        patch.object(NegocioService, "get", new=AsyncMock()) as business,
        patch.object(ValeService, "_commit", new=AsyncMock()),
    ):
        updated = await ValeService.update(
            MagicMock(),
            vale.id,
            ValeUpdate(categoria_id=categoria_id, negocio_id=negocio_id),
            uuid4(),
        )
    assert updated.categoria_id == categoria_id
    assert updated.negocio_id == negocio_id
    category.assert_awaited_once()
    business.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_aplica_soft_delete() -> None:
    vale = _vale()
    actor_id = uuid4()
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(ValeService, "_commit", new=AsyncMock()),
    ):
        deleted = await ValeService.delete(MagicMock(), vale.id, actor_id)
    assert deleted.is_deleted is True
    assert deleted.deleted_by == actor_id
    assert deleted.deleted_at == deleted.updated_at


@pytest.mark.asyncio
async def test_commit_traduce_integrity_error() -> None:
    session = _session()
    session.commit.side_effect = IntegrityError(None, None, Exception("constraint"))
    with pytest.raises(AppException) as error:
        await ValeService._commit(session, _vale())
    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_image_reemplaza_anterior() -> None:
    old_url = "https://res.cloudinary.com/demo/image/upload/old.jpg"
    new_url = "https://res.cloudinary.com/demo/image/upload/new.jpg"
    vale = _vale(image_url=old_url)
    session = _session()
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(ValeService, "_commit_transaction", new=AsyncMock()),
        patch.object(
            CloudinaryService,
            "upload_image",
            new=AsyncMock(return_value={"url": new_url}),
        ),
        patch.object(
            CloudinaryService, "safe_delete_image", new=AsyncMock()
        ) as delete_image,
    ):
        updated = await ValeService.upload_image(
            session,
            vale.id,
            MagicMock(spec=UploadFile),
            uuid4(),
            MagicMock(spec=Settings),
        )
    assert updated.image_url == new_url
    delete_image.assert_awaited_once_with(old_url)
    session.refresh.assert_awaited_once_with(vale)


@pytest.mark.asyncio
async def test_delete_image_sin_imagen_es_idempotente() -> None:
    vale = _vale(image_url=None)
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(ValeService, "_commit", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService, "safe_delete_image", new=AsyncMock()
        ) as delete_image,
    ):
        updated = await ValeService.delete_image(MagicMock(), vale.id, uuid4())
    assert updated is vale
    commit.assert_not_awaited()
    delete_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_image_limpia_url_y_cloudinary() -> None:
    url = "https://res.cloudinary.com/demo/image/upload/vale.jpg"
    vale = _vale(image_url=url)
    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=vale)),
        patch.object(ValeService, "_commit", new=AsyncMock()) as commit,
        patch.object(
            CloudinaryService, "safe_delete_image", new=AsyncMock()
        ) as delete_image,
    ):
        updated = await ValeService.delete_image(MagicMock(), vale.id, uuid4())
    assert updated.image_url is None
    commit.assert_awaited_once()
    delete_image.assert_awaited_once_with(url)
