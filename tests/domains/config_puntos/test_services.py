from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.schemas import (
    ConfigPuntosCreate,
    FactorPuntosInput,
)
from app.domains.config_puntos.services import ConfigPuntosService
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


def _config(**overrides: object) -> ConfigPuntos:
    values: dict[str, object] = {
        "start_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "end_date": None,
        "factor_asignacion_puntos": Decimal("0.100000"),
        "factor_costo_vale": Decimal("10.000000"),
    }
    values.update(overrides)
    return ConfigPuntos(**values)


def _create_data() -> ConfigPuntosCreate:
    return ConfigPuntosCreate(
        asignacion=FactorPuntosInput(cant_bs=100, cant_puntos=10),
        costo_vale=FactorPuntosInput(cant_bs=50, cant_puntos=500),
    )


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


def test_calculate_factor_divide_puntos_entre_bs_y_redondea() -> None:
    factor = ConfigPuntosService._calculate_factor(
        FactorPuntosInput(cant_bs=3, cant_puntos=1),
        "asignacion",
    )

    assert factor == Decimal("0.333333")


def test_calculate_factor_rechaza_resultado_que_redondea_a_cero() -> None:
    with pytest.raises(AppException) as error:
        ConfigPuntosService._calculate_factor(
            FactorPuntosInput(cant_bs=2_147_483_647, cant_puntos=1),
            "asignacion",
        )

    assert error.value.status_code == 422
    assert "asignacion" in error.value.details


def test_calculate_factor_rechaza_resultado_que_excede_numeric() -> None:
    with pytest.raises(AppException) as error:
        ConfigPuntosService._calculate_factor(
            FactorPuntosInput(cant_bs=1, cant_puntos=1_000_000_000_000),
            "costo_vale",
        )

    assert error.value.status_code == 422
    assert "costo_vale" in error.value.details


@pytest.mark.asyncio
async def test_get_rechaza_configuracion_inexistente() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await ConfigPuntosService.get(session, uuid4())

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_get_active_rechaza_si_no_existe_configuracion() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await ConfigPuntosService.get_active(session)

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_devuelve_historial_paginado() -> None:
    config = _config()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [config]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await ConfigPuntosService.list(session, page=1, per_page=10)

    assert page.total == 1
    assert page.total_pages == 1
    assert page.data[0].id == config.id


@pytest.mark.asyncio
@pytest.mark.parametrize(("page", "per_page"), [(0, 20), (1, 0), (1, 101)])
async def test_list_rechaza_paginacion_invalida(page: int, per_page: int) -> None:
    with pytest.raises(AppException) as error:
        await ConfigPuntosService.list(MagicMock(), page=page, per_page=per_page)

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_replace_crea_primera_configuracion_con_factores_calculados() -> None:
    session = _session()
    actor_id = uuid4()

    with patch.object(
        ConfigPuntosService,
        "get_active",
        new=AsyncMock(return_value=None),
    ):
        config = await ConfigPuntosService.replace(
            session,
            _create_data(),
            actor_id,
        )

    assert config.factor_asignacion_puntos == Decimal("0.100000")
    assert config.factor_costo_vale == Decimal("10.000000")
    assert config.created_by == actor_id
    assert config.updated_by == actor_id
    session.add.assert_called_once_with(config)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(config)


@pytest.mark.asyncio
async def test_replace_cierra_configuracion_anterior() -> None:
    session = _session()
    actor_id = uuid4()
    active_config = _config()

    with patch.object(
        ConfigPuntosService,
        "get_active",
        new=AsyncMock(return_value=active_config),
    ):
        new_config = await ConfigPuntosService.replace(
            session,
            _create_data(),
            actor_id,
        )

    assert active_config.end_date == new_config.start_date
    assert active_config.updated_at == new_config.start_date
    assert active_config.updated_by == actor_id
    assert new_config.end_date is None


@pytest.mark.asyncio
async def test_replace_traduce_conflicto_de_configuracion_activa() -> None:
    original_error = MagicMock()
    original_error.constraint_name = "uq_config_puntos_activa"
    session = _session()
    session.commit.side_effect = IntegrityError(None, None, original_error)

    with patch.object(
        ConfigPuntosService,
        "get_active",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(AppException) as error:
            await ConfigPuntosService.replace(session, _create_data(), uuid4())

    assert error.value.status_code == 409
    assert error.value.code == ErrorCode.CONFLICT
    session.rollback.assert_awaited_once()
