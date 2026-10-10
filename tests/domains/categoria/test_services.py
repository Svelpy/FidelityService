from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domains.categoria.models import Categoria
from app.domains.categoria.schemas import CategoriaCreate, CategoriaUpdate
from app.domains.categoria.services import CategoriaService
from app.shared.errors.exceptions import AppException


def _session_with_scalar(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_genera_slug_y_auditoria() -> None:
    session = _session_with_scalar(None)
    actor_id = uuid4()

    categoria = await CategoriaService.create(
        session,
        CategoriaCreate(
            nombre="Gastronomía y Café",
            icon_number=3,
            descripcion=None,
        ),
        actor_id,
    )

    assert categoria.slug == "gastronomia-y-cafe"
    assert categoria.created_by == actor_id
    assert categoria.updated_by == actor_id
    assert categoria.is_deleted is False
    session.add.assert_called_once_with(categoria)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(categoria)


@pytest.mark.asyncio
async def test_create_rechaza_slug_duplicado() -> None:
    session = _session_with_scalar(uuid4())

    with pytest.raises(AppException) as error:
        await CategoriaService.create(
            session,
            CategoriaCreate(nombre="Gastronomía", icon_number=3),
            uuid4(),
        )

    assert error.value.status_code == 409
    assert error.value.details == {
        "nombre": "El nombre genera un slug que ya está registrado."
    }
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_conserva_null_explicito_para_descripcion() -> None:
    categoria = Categoria(
        nombre="Gastronomía",
        slug="gastronomia",
        icon_number=3,
        descripcion="Descripción anterior",
    )
    actor_id = uuid4()

    with (
        patch.object(
            CategoriaService,
            "get",
            new=AsyncMock(return_value=categoria),
        ),
        patch.object(CategoriaService, "_commit", new=AsyncMock()) as commit,
    ):
        updated = await CategoriaService.update(
            MagicMock(),
            categoria.id,
            CategoriaUpdate(descripcion=None),
            actor_id,
        )

    assert updated.descripcion is None
    assert updated.updated_by == actor_id
    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_aplica_soft_delete_y_auditoria() -> None:
    categoria = Categoria(
        nombre="Gastronomía",
        slug="gastronomia",
        icon_number=3,
    )
    actor_id = uuid4()

    with (
        patch.object(
            CategoriaService,
            "get",
            new=AsyncMock(return_value=categoria),
        ),
        patch.object(CategoriaService, "_commit", new=AsyncMock()) as commit,
    ):
        deleted = await CategoriaService.delete(
            MagicMock(),
            categoria.id,
            actor_id,
        )

    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    assert deleted.deleted_by == actor_id
    assert deleted.updated_at == deleted.deleted_at
    assert deleted.updated_by == actor_id
    commit.assert_awaited_once()
