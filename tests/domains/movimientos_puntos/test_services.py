from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.shared.enums import Genero, Role, TipoMovimiento, TipoNegocio
from app.shared.errors.exceptions import AppException


def _user(*, points: int = 10) -> User:
    return User(
        nombre="Ana",
        ci="12345678",
        telefono="71234567",
        role=Role.CLIENTE,
        genero=Genero.F,
        puntos=points,
        password_hash="hash",
    )


def _async_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    return session


def _movement() -> MovimientoPuntos:
    return MovimientoPuntos(
        usuario_id=uuid4(),
        tipo_movimiento=TipoMovimiento.ACUMULA,
        puntos=10,
        operacion_id=uuid4(),
        canje_id=None,
    )


@pytest.mark.asyncio
async def test_get_detail_devuelve_relaciones_en_una_consulta() -> None:
    business = Negocio(nombre="Negocio", tipo=TipoNegocio.SOCIO)
    branch = Sucursal(nombre="Central", negocio_id=business.id)
    operation = Operacion(
        receptor_id=uuid4(),
        emisor_id=uuid4(),
        total_compra="100.00",
        total_puntos=10,
        config_punto_id=uuid4(),
        sucursal_id=branch.id,
    )
    movement = MovimientoPuntos(
        usuario_id=operation.receptor_id,
        tipo_movimiento=TipoMovimiento.ACUMULA,
        puntos=operation.total_puntos,
        operacion_id=operation.id,
        canje_id=None,
    )
    result = MagicMock()
    result.one_or_none.return_value = (
        movement,
        None,
        operation,
        branch,
        business,
    )
    session = _async_session()
    session.execute.return_value = result

    detail = await MovimientoPuntosService.get_detail(
        session,
        movement.id,
        uuid4(),
        Role.ADMIN,
    )

    assert detail.data.id == movement.id
    assert detail.canje is None
    assert detail.operacion is not None
    assert detail.operacion.id == operation.id
    assert detail.sucursal is not None
    assert detail.sucursal.id == branch.id
    assert detail.negocio is not None
    assert detail.negocio.id == business.id
    session.execute.assert_awaited_once()
    sql = str(session.execute.await_args.args[0].compile())
    assert sql.count("LEFT OUTER JOIN") == 5


@pytest.mark.asyncio
async def test_get_detail_oculta_movimiento_ajeno_al_cliente() -> None:
    result = MagicMock()
    result.one_or_none.return_value = None
    session = _async_session()
    session.execute.return_value = result
    actor_id = uuid4()

    with pytest.raises(AppException) as error:
        await MovimientoPuntosService.get_detail(
            session,
            uuid4(),
            actor_id,
            Role.CLIENTE,
        )

    assert error.value.status_code == 404
    compiled = session.execute.await_args.args[0].compile()
    assert actor_id in compiled.params.values()


def test_register_accrual_actualiza_saldo_y_agrega_movimiento_sin_commit() -> None:
    session = MagicMock()
    user = _user(points=10)
    actor_id = uuid4()
    operation_id = uuid4()
    occurred_at = datetime.now(timezone.utc)

    movement = MovimientoPuntosService.register_accrual(
        session,
        user,
        15,
        operation_id,
        actor_id,
        occurred_at,
    )

    assert user.puntos == 25
    assert user.updated_by == actor_id
    assert movement.usuario_id == user.id
    assert movement.tipo_movimiento is TipoMovimiento.ACUMULA
    assert movement.puntos == 15
    assert movement.operacion_id == operation_id
    assert movement.canje_id is None
    session.add.assert_called_once_with(movement)
    session.commit.assert_not_called()


@pytest.mark.parametrize("points", [0, -1])
def test_register_accrual_rechaza_puntos_no_positivos(points: int) -> None:
    session = MagicMock()
    user = _user()

    with pytest.raises(AppException) as error:
        MovimientoPuntosService.register_accrual(
            session,
            user,
            points,
            uuid4(),
            uuid4(),
            datetime.now(timezone.utc),
        )

    assert error.value.status_code == 422
    assert user.puntos == 10
    session.add.assert_not_called()


def test_register_redemption_descuenta_saldo_y_agrega_movimiento() -> None:
    session = MagicMock()
    user = _user(points=500)
    actor_id = uuid4()
    redemption_id = uuid4()
    occurred_at = datetime.now(timezone.utc)

    movement = MovimientoPuntosService.register_redemption(
        session,
        user,
        200,
        redemption_id,
        actor_id,
        occurred_at,
    )

    assert user.puntos == 300
    assert movement.tipo_movimiento is TipoMovimiento.CANJE
    assert movement.puntos == 200
    assert movement.operacion_id is None
    assert movement.canje_id == redemption_id
    session.add.assert_called_once_with(movement)
    session.commit.assert_not_called()


def test_register_redemption_rechaza_saldo_insuficiente() -> None:
    session = MagicMock()
    user = _user(points=100)

    with pytest.raises(AppException) as error:
        MovimientoPuntosService.register_redemption(
            session,
            user,
            101,
            uuid4(),
            uuid4(),
            datetime.now(timezone.utc),
        )

    assert error.value.status_code == 409
    assert user.puntos == 100
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_list_for_user_devuelve_historial_paginado() -> None:
    session = _async_session()
    movement = _movement()
    total_result = MagicMock()
    total_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [movement]
    session.execute.side_effect = [total_result, rows_result]

    page = await MovimientoPuntosService.list_for_user(
        session,
        movement.usuario_id,
        page=1,
        per_page=20,
        movement_type=TipoMovimiento.ACUMULA,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert len(page.data) == 1
    assert page.data[0].id == movement.id
    assert page.data[0].tipo_movimiento is TipoMovimiento.ACUMULA


@pytest.mark.asyncio
async def test_list_by_user_id_rechaza_cliente() -> None:
    session = _async_session()

    with pytest.raises(AppException) as error:
        await MovimientoPuntosService.list_by_user_id(
            session,
            uuid4(),
            Role.CLIENTE,
        )

    assert error.value.status_code == 403
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_by_user_id_valida_usuario_y_delega_historial() -> None:
    session = _async_session()
    user_id = uuid4()
    expected_page = MagicMock()

    with (
        patch.object(UserService, "get", new=AsyncMock()) as get_user,
        patch.object(
            MovimientoPuntosService,
            "list_for_user",
            new=AsyncMock(return_value=expected_page),
        ) as list_for_user,
    ):
        page = await MovimientoPuntosService.list_by_user_id(
            session,
            user_id,
            Role.CAJERO,
            page=2,
            per_page=10,
        )

    assert page is expected_page
    get_user.assert_awaited_once_with(session, user_id)
    list_for_user.assert_awaited_once_with(
        session,
        user_id,
        page=2,
        per_page=10,
        movement_type=None,
    )
