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
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.services import SucursalService
from app.domains.users.models import User
from app.domains.users.schemas import UserRegistrationData
from app.domains.users.services import UserService
from app.shared.enums import Genero, Role, TipoMovimiento
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
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


def _receptor_data() -> UserRegistrationData:
    return UserRegistrationData(
        ci="12345678",
        telefono="71234567",
        nombre="Cliente",
        genero=Genero.O,
    )


def test_calculate_points_redondea_hacia_abajo() -> None:
    assert OperacionService._calculate_points(
        Decimal("35.99"),
        100,
        10,
    ) == 3


def test_calculate_points_rechaza_compra_que_no_genera_un_punto() -> None:
    with pytest.raises(AppException) as error:
        OperacionService._calculate_points(
            Decimal("5.00"),
            100,
            10,
        )

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_create_registra_operacion_saldo_y_movimiento_atomicamente() -> None:
    session = _session()
    actor_id = uuid4()
    branch_id = uuid4()
    client = _client(points=20)
    config = ConfigPuntos(
        asignacion_bolivianos=100,
        asignacion_puntos=10,
        costo_vale_bolivianos=50,
        costo_vale_puntos=500,
    )

    with (
        patch.object(SucursalService, "get", new=AsyncMock()) as get_branch,
        patch.object(
            UserService,
            "get",
            new=AsyncMock(return_value=client),
        ) as get_user,
        patch.object(UserService, "register", new=AsyncMock()) as register_user,
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
                receptor_data=_receptor_data(),
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
    register_user.assert_not_awaited()
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(operation)


@pytest.mark.asyncio
async def test_create_rechaza_receptor_id_inexistente_sin_registrarlo() -> None:
    session = _session()
    actor_id = uuid4()
    branch_id = uuid4()
    requested_recipient_id = uuid4()
    registration_data = _receptor_data()
    not_found = AppException(
        "Usuario no encontrado.",
        404,
        ErrorCode.RESOURCE_NOT_FOUND,
    )

    with (
        patch.object(SucursalService, "get", new=AsyncMock()),
        patch.object(UserService, "get", new=AsyncMock(side_effect=not_found)) as get_user,
        patch.object(UserService, "register", new=AsyncMock()) as register_user,
    ):
        with pytest.raises(AppException) as error:
            await OperacionService.create(
                session,
                OperacionCreate(
                    receptor_id=requested_recipient_id,
                    receptor_data=registration_data,
                    total_compra="100.00",
                ),
                actor_id,
                branch_id,
            )

    get_user.assert_awaited_once_with(
        session,
        requested_recipient_id,
        for_update=True,
    )
    assert error.value.status_code == 404
    register_user.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_registra_receptor_cuando_id_es_nulo() -> None:
    session = _session()
    actor_id = uuid4()
    branch_id = uuid4()
    new_client = _client(points=0)
    registration_data = _receptor_data()
    config = ConfigPuntos(
        asignacion_bolivianos=100,
        asignacion_puntos=10,
        costo_vale_bolivianos=50,
        costo_vale_puntos=500,
    )

    with (
        patch.object(SucursalService, "get", new=AsyncMock()),
        patch.object(UserService, "get", new=AsyncMock()) as get_user,
        patch.object(
            UserService,
            "register",
            new=AsyncMock(return_value=new_client),
        ) as register_user,
        patch.object(
            ConfigPuntosService,
            "get_active",
            new=AsyncMock(return_value=config),
        ),
    ):
        operation = await OperacionService.create(
            session,
            OperacionCreate(
                receptor_id=None,
                receptor_data=registration_data,
                total_compra="100.00",
            ),
            actor_id,
            branch_id,
        )

    get_user.assert_not_awaited()
    register_user.assert_awaited_once_with(
        session,
        registration_data,
        commit=False,
    )
    assert operation.receptor_id == new_client.id
    assert new_client.role is Role.CLIENTE
    assert new_client.sucursal_id is None
    assert new_client.puntos == 10
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_requiere_sucursal_del_emisor() -> None:
    session = _session()

    with pytest.raises(AppException) as error:
        await OperacionService.create(
            session,
            OperacionCreate(
                receptor_id=uuid4(),
                receptor_data=_receptor_data(),
                total_compra="100.00",
            ),
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
                OperacionCreate(
                    receptor_id=recipient.id,
                    receptor_data=_receptor_data(),
                    total_compra="100.00",
                ),
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
    recipient = _client()
    recipient.id = operation.receptor_id
    recipient.apellidos = "Pérez López"
    issuer = User(
        id=operation.emisor_id,
        nombre="María",
        apellidos="Gómez Rojas",
        ci="87654321",
        telefono="71234568",
        role=Role.CAJERO,
        genero=Genero.F,
        password_hash="hash",
    )
    branch = Sucursal(
        id=operation.sucursal_id,
        nombre="Sucursal Central",
        negocio_id=uuid4(),
    )
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [(operation, recipient, issuer, branch)]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await OperacionService.list(
        session,
        operation.receptor_id,
        Role.ADMIN,
        page=1,
        per_page=10,
        emisor_id=operation.emisor_id,
        receptor_id=operation.receptor_id,
        sucursal_id=operation.sucursal_id,
    )

    assert page.total == 1
    assert len(page.data) == 1
    assert page.data[0].id == operation.id
    assert page.data[0].receptor.id == recipient.id
    assert page.data[0].receptor.apellidos == "Pérez López"
    assert page.data[0].emisor.id == issuer.id
    assert page.data[0].emisor.role is Role.CAJERO
    assert page.data[0].sucursal.nombre == "Sucursal Central"
    count_statement = session.execute.await_args_list[0].args[0]
    rows_statement = session.execute.await_args_list[1].args[0]
    for statement in (count_statement, rows_statement):
        parameters = statement.compile().params.values()
        assert operation.emisor_id in parameters
        assert operation.receptor_id in parameters
        assert operation.sucursal_id in parameters
