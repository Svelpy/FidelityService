from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.operacion.models import Operacion
from app.domains.operacion.schemas import OperacionCreate
from app.domains.operacion.services import OperacionService
from app.domains.sucursal.services import SucursalService
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.shared.enums import Genero, Role, TipoMovimiento
from app.shared.errors.exceptions import AppException


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _client(*, points: int = 20) -> User:
    return User(
        nombre="Cliente",
        ci="12345678",
        telefono="71234567",
        role=Role.CLIENTE,
        genero=Genero.O,
        puntos=points,
        password_hash="hash",
    )


def test_calculate_points_redondea_hacia_abajo() -> None:
    assert OperacionService._calculate_points(
        Decimal("35.99"),
        Decimal("0.100000"),
    ) == 3


def test_calculate_points_rechaza_compra_que_no_genera_un_punto() -> None:
    with pytest.raises(AppException) as error:
        OperacionService._calculate_points(
            Decimal("5.00"),
            Decimal("0.100000"),
        )

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_create_registra_operacion_saldo_y_movimiento_atomicamente() -> None:
    session = _session()
    actor_id = uuid4()
    branch_id = uuid4()
    client = _client(points=20)
    config = ConfigPuntos(
        factor_asignacion_puntos=Decimal("0.100000"),
        factor_costo_vale=Decimal("10.000000"),
    )

    with (
        patch.object(SucursalService, "get", new=AsyncMock()) as get_branch,
        patch.object(
            UserService,
            "get",
            new=AsyncMock(return_value=client),
        ) as get_user,
        patch.object(
            ConfigPuntosService,
            "get_active",
            new=AsyncMock(return_value=config),
        ),
    ):
        operation = await OperacionService.create(
            session,
            OperacionCreate(
                receptor_id=client.id,
                total_compra=Decimal("150.00"),
                referencia="Factura 123",
            ),
            actor_id,
            branch_id,
        )

    assert operation.total_puntos == 15
    assert operation.emisor_id == actor_id
    assert operation.sucursal_id == branch_id
    assert client.puntos == 35
    added = [call.args[0] for call in session.add.call_args_list]
    assert operation in added
    movement = next(item for item in added if isinstance(item, MovimientoPuntos))
    assert movement.tipo_movimiento is TipoMovimiento.ACUMULA
    assert movement.operacion_id == operation.id
    get_branch.assert_awaited_once_with(session, branch_id)
    get_user.assert_awaited_once_with(session, client.id, for_update=True)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(operation)


@pytest.mark.asyncio
async def test_create_requiere_sucursal_del_emisor() -> None:
    session = _session()

    with pytest.raises(AppException) as error:
        await OperacionService.create(
            session,
            OperacionCreate(receptor_id=uuid4(), total_compra="100.00"),
            uuid4(),
            None,
        )

    assert error.value.status_code == 422
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_requiere_receptor_cliente() -> None:
    session = _session()
    recipient = _client()
    recipient.role = Role.CAJERO

    with (
        patch.object(SucursalService, "get", new=AsyncMock()),
        patch.object(UserService, "get", new=AsyncMock(return_value=recipient)),
    ):
        with pytest.raises(AppException) as error:
            await OperacionService.create(
                session,
                OperacionCreate(receptor_id=recipient.id, total_compra="100.00"),
                uuid4(),
                uuid4(),
            )

    assert error.value.status_code == 422
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_oculta_operacion_fuera_del_alcance() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = _session()
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await OperacionService.get(
            session,
            uuid4(),
            uuid4(),
            Role.CLIENTE,
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_list_devuelve_operaciones_visibles_paginadas() -> None:
    operation = Operacion(
        receptor_id=uuid4(),
        emisor_id=uuid4(),
        total_compra=Decimal("100.00"),
        total_puntos=10,
        config_punto_id=uuid4(),
        sucursal_id=uuid4(),
    )
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [operation]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await OperacionService.list(
        session,
        operation.receptor_id,
        Role.CLIENTE,
        page=1,
        per_page=10,
    )

    assert page.total == 1
    assert len(page.data) == 1
    assert page.data[0].id == operation.id
