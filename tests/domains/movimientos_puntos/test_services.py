from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.domains.canje.models import Canje
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.vale.models import Vale
from app.shared.enums import EstadoCanje, Genero, Role, TipoMovimiento, TipoNegocio
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
    assert sql.count("LEFT OUTER JOIN") == 6


@pytest.mark.asyncio
async def test_get_detail_oculta_movimiento_ajeno_al_cajero() -> None:
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
            Role.CAJERO,
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


def test_register_adjustment_repone_saldo_y_conserva_movimiento_origen() -> None:
    session = MagicMock()
    user = _user(points=300)
    actor_id = uuid4()
    movement_origin_id = uuid4()
    occurred_at = datetime.now(timezone.utc)

    movement = MovimientoPuntosService.register_adjustment(
        session,
        user,
        200,
        actor_id,
        occurred_at,
        movement_origin_id,
    )

    assert user.puntos == 500
    assert user.updated_by == actor_id
    assert movement.tipo_movimiento is TipoMovimiento.AJUSTE
    assert movement.puntos == 200
    assert movement.operacion_id is None
    assert movement.canje_id is None
    assert movement.movimiento_origen_id == movement_origin_id
    session.add.assert_called_once_with(movement)
    session.commit.assert_not_called()


def _accrual(user: User, points: int) -> MovimientoPuntos:
    return MovimientoPuntos(
        usuario_id=user.id,
        tipo_movimiento=TipoMovimiento.ACUMULA,
        puntos=points,
        operacion_id=uuid4(),
    )


def test_register_reversal_descuenta_saldo_y_referencia_acumulacion() -> None:
    session = MagicMock()
    user = _user(points=1000)
    accrual = _accrual(user, 900)
    actor_id = uuid4()
    occurred_at = datetime.now(timezone.utc)

    movement = MovimientoPuntosService.register_reversal(
        session,
        user,
        accrual,
        actor_id,
        occurred_at,
    )

    assert user.puntos == 100
    assert user.updated_by == actor_id
    assert movement.tipo_movimiento is TipoMovimiento.REVERSA
    assert movement.puntos == 900
    assert movement.operacion_id is None
    assert movement.canje_id is None
    assert movement.movimiento_origen_id == accrual.id
    assert movement.created_by == actor_id
    session.add.assert_called_once_with(movement)
    session.commit.assert_not_called()


def test_register_reversal_rechaza_saldo_insuficiente() -> None:
    session = MagicMock()
    user = _user(points=50)
    accrual = _accrual(user, 900)

    with pytest.raises(AppException) as error:
        MovimientoPuntosService.register_reversal(
            session,
            user,
            accrual,
            uuid4(),
            datetime.now(timezone.utc),
        )

    assert error.value.status_code == 409
    assert user.puntos == 50
    session.add.assert_not_called()


def test_register_reversal_rechaza_movimiento_que_no_es_acumulacion() -> None:
    session = MagicMock()
    user = _user(points=1000)
    accrual = _accrual(user, 100)
    accrual.tipo_movimiento = TipoMovimiento.CANJE

    with pytest.raises(AppException) as error:
        MovimientoPuntosService.register_reversal(
            session,
            user,
            accrual,
            uuid4(),
            datetime.now(timezone.utc),
        )

    assert error.value.status_code == 409
    assert user.puntos == 1000
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_list_administrativo_devuelve_relaciones_y_aplica_filtros() -> None:
    session = _async_session()
    movement = _movement()
    client = _user()
    client.id = movement.usuario_id
    emitter = _user()
    emitter.id = uuid4()
    emitter.role = Role.CAJERO
    operation = Operacion(
        id=movement.operacion_id,
        receptor_id=client.id,
        emisor_id=emitter.id,
        total_compra=Decimal("100.00"),
        total_puntos=movement.puntos,
        config_punto_id=uuid4(),
        sucursal_id=uuid4(),
    )
    total_result = MagicMock()
    total_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (movement, client, emitter, operation, None, None)
    ]
    session.execute.side_effect = [total_result, rows_result]

    page = await MovimientoPuntosService.list(
        session,
        uuid4(),
        Role.ADMIN,
        page=1,
        per_page=20,
        user_id=client.id,
        movement_type=TipoMovimiento.ACUMULA,
    )

    assert page.total == 1
    assert page.total_pages == 1
    assert len(page.data) == 1
    assert page.data[0].movimiento.id == movement.id
    assert page.data[0].cliente.id == client.id
    assert page.data[0].emisor is not None
    assert page.data[0].emisor.id == emitter.id
    assert page.data[0].operacion is not None
    assert page.data[0].operacion.id == operation.id
    assert page.data[0].canje is None
    assert page.data[0].vale is None
    parameters = session.execute.await_args_list[1].args[0].compile().params.values()
    assert client.id in parameters
    assert TipoMovimiento.ACUMULA in parameters


@pytest.mark.asyncio
async def test_list_me_devuelve_movimiento_con_canje_y_vale() -> None:
    session = _async_session()
    user_id = uuid4()
    voucher = Vale(
        total_costo=Decimal("50.00"),
        total_puntos=500,
        nombre="Vale",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    redemption = Canje(
        cliente_id=user_id,
        dador_id=None,
        vale_id=voucher.id,
        status=EstadoCanje.PENDIENTE,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        codigo_canje="00123456",
        sucursal_id=None,
        total_puntos=voucher.total_puntos,
        total_costo=voucher.total_costo,
        referencia=None,
        config_punto_id=uuid4(),
    )
    movement = MovimientoPuntos(
        usuario_id=user_id,
        tipo_movimiento=TipoMovimiento.CANJE,
        puntos=500,
        operacion_id=None,
        canje_id=redemption.id,
    )
    total_result = MagicMock()
    total_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [(movement, None, redemption, voucher)]
    session.execute.side_effect = [total_result, rows_result]

    page = await MovimientoPuntosService.list_me(session, user_id)

    assert page.total == 1
    assert page.data[0].movimiento.id == movement.id
    assert page.data[0].operacion is None
    assert page.data[0].canje is not None
    assert page.data[0].canje.id == redemption.id
    assert page.data[0].vale is not None
    assert page.data[0].vale.id == voucher.id


@pytest.mark.asyncio
async def test_list_cliente_no_ve_movimientos_fuera_de_me() -> None:
    session = _async_session()
    total_result = MagicMock()
    total_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.all.return_value = []
    session.execute.side_effect = [total_result, rows_result]
    actor_id = uuid4()

    await MovimientoPuntosService.list(session, actor_id, Role.CLIENTE)

    for call in session.execute.await_args_list:
        sql = str(call.args[0].compile())
        assert "movimientos_puntos.id IS NULL" in sql
        assert actor_id not in call.args[0].compile().params.values()


@pytest.mark.parametrize("role", [Role.SUPERADMIN, Role.OWNER, Role.ADMIN])
def test_visibility_filters_roles_globales_ven_todo(role: Role) -> None:
    assert MovimientoPuntosService._visibility_filters(uuid4(), role) == []


def test_visibility_filters_cajero_ve_solo_movimientos_de_sus_acciones() -> None:
    actor_id = uuid4()

    (condition,) = MovimientoPuntosService._visibility_filters(actor_id, Role.CAJERO)

    compiled = condition.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    # ACUMULA de operaciones que emitió.
    assert "movimientos_puntos.operacion_id IN" in sql
    assert "emisor_id = " in sql
    # CANJE de canjes que entregó.
    assert "movimientos_puntos.canje_id IN" in sql
    assert "dador_id = " in sql
    # AJUSTE de canjes que canceló.
    assert "movimientos_puntos.tipo_movimiento = " in sql
    assert "movimientos_puntos.created_by = " in sql
    # Ya no depende del negocio ni de la sucursal.
    assert "negocio_id" not in sql
    assert "sucursal" not in sql
    # REVERSA de acumulaciones de operaciones que emitió.
    assert "movimientos_puntos.movimiento_origen_id IN" in sql
    params = list(compiled.params.values())
    assert params.count(actor_id) == 3
    assert TipoMovimiento.AJUSTE in params
    assert TipoMovimiento.REVERSA in params


@pytest.mark.parametrize("role", [Role.SOCIO, Role.CLIENTE])
def test_visibility_filters_deniega_roles_no_contemplados(role: Role) -> None:
    (condition,) = MovimientoPuntosService._visibility_filters(uuid4(), role)

    assert str(condition.compile()).endswith("movimientos_puntos.id IS NULL")


@pytest.mark.asyncio
async def test_get_detail_cajero_aplica_alcance_de_sus_acciones() -> None:
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
            Role.CAJERO,
        )

    assert error.value.status_code == 404
    compiled = session.execute.await_args.args[0].compile()
    assert actor_id in compiled.params.values()
    assert "dador_id" in str(compiled)
