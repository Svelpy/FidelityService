from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domains.canje.models import Canje
from app.domains.canje.schemas import CanjeCreate
from app.domains.canje.services import CanjeService
from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.models import Negocio
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.services import SucursalService
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.domains.vale.models import Vale
from app.domains.vale.services import ValeService
from app.shared.enums import (
    EstadoCanje,
    Genero,
    Role,
    TipoMovimiento,
    TipoNegocio,
)
from app.shared.errors.exceptions import AppException


def _session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


def _client(*, points: int = 1_000) -> User:
    return User(
        nombre="Cliente",
        ci="12345678",
        telefono="71234567",
        role=Role.CLIENTE,
        genero=Genero.O,
        puntos=points,
        password_hash="hash",
    )


def _redemption(**overrides: object) -> Canje:
    values: dict[str, object] = {
        "cliente_id": uuid4(),
        "dador_id": None,
        "vale_id": uuid4(),
        "status": EstadoCanje.PENDIENTE,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        "codigo_canje": "00123456",
        "sucursal_id": None,
        "total_puntos": 500,
        "total_costo": Decimal("50.00"),
        "referencia": None,
        "config_punto_id": uuid4(),
    }
    values.update(overrides)
    return Canje(**values)


@pytest.mark.asyncio
async def test_list_aplica_todos_los_filtros_solicitados() -> None:
    redemption = _redemption(
        dador_id=uuid4(),
        status=EstadoCanje.CANJEADO,
        sucursal_id=uuid4(),
    )
    voucher = Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    business = Negocio(
        id=voucher.negocio_id,
        nombre="Café Central",
        tipo=TipoNegocio.SOCIO,
    )
    branch = Sucursal(
        id=redemption.sucursal_id,
        nombre="Central",
        negocio_id=business.id,
    )
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [(redemption, voucher, branch, business)]
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await CanjeService.list(
        session,
        uuid4(),
        Role.ADMIN,
        None,
        page=1,
        per_page=10,
        cliente_id=redemption.cliente_id,
        dador_id=redemption.dador_id,
        vale_id=redemption.vale_id,
        status=redemption.status,
        sucursal_id=redemption.sucursal_id,
        negocio_id=business.id,
    )

    assert page.total == 1
    assert page.data[0].canje.id == redemption.id
    assert page.data[0].vale.id == voucher.id
    assert page.data[0].sucursal is not None
    assert page.data[0].sucursal.id == branch.id
    assert page.data[0].negocio.id == business.id
    for call in session.execute.await_args_list:
        parameters = call.args[0].compile().params.values()
        assert redemption.cliente_id in parameters
        assert redemption.dador_id in parameters
        assert redemption.vale_id in parameters
        assert redemption.status in parameters
        assert redemption.sucursal_id in parameters
        assert business.id in parameters


@pytest.mark.asyncio
async def test_list_for_user_incluye_cliente_o_dador() -> None:
    user_id = uuid4()
    redemptions = [
        _redemption(cliente_id=user_id),
        _redemption(dador_id=user_id, status=EstadoCanje.CANJEADO, sucursal_id=uuid4()),
    ]
    vouchers = [
        Vale(
            id=redemption.vale_id,
            total_costo=redemption.total_costo,
            total_puntos=redemption.total_puntos,
            nombre="Vale Bs 50",
            categoria_id=uuid4(),
            negocio_id=uuid4(),
        )
        for redemption in redemptions
    ]
    businesses = [
        Negocio(id=voucher.negocio_id, nombre="Café Central", tipo=TipoNegocio.SOCIO)
        for voucher in vouchers
    ]
    branches = [
        None,
        Sucursal(
            id=redemptions[1].sucursal_id,
            nombre="Central",
            negocio_id=businesses[1].id,
        ),
    ]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    rows_result = MagicMock()
    rows_result.all.return_value = list(
        zip(redemptions, vouchers, branches, businesses, strict=True)
    )
    session = _session()
    session.execute.side_effect = [count_result, rows_result]

    page = await CanjeService.list_for_user(
        session,
        user_id,
        page=1,
        per_page=10,
        status=EstadoCanje.CANJEADO,
        vale_id=redemptions[1].vale_id,
        negocio_id=businesses[1].id,
        sucursal_id=redemptions[1].sucursal_id,
    )

    assert page.total == 2
    assert [item.canje.id for item in page.data] == [
        item.id for item in redemptions
    ]
    assert [item.vale.id for item in page.data] == [item.id for item in vouchers]
    assert [item.negocio.id for item in page.data] == [
        item.id for item in businesses
    ]
    assert page.data[0].sucursal is None
    assert page.data[1].sucursal is not None
    assert page.data[1].sucursal.id == branches[1].id
    assert "created_by" not in page.data[0].model_dump()["negocio"]
    for call in session.execute.await_args_list:
        statement = call.args[0]
        compiled = statement.compile()
        assert list(compiled.params.values()).count(user_id) == 2
        sql = str(compiled)
        assert "canje.cliente_id" in sql
        assert "canje.dador_id" in sql
        assert " OR " in sql
        parameters = compiled.params.values()
        assert EstadoCanje.CANJEADO in parameters
        assert redemptions[1].vale_id in parameters
        assert businesses[1].id in parameters
        assert redemptions[1].sucursal_id in parameters


@pytest.mark.asyncio
async def test_get_devuelve_canje_y_vale_en_una_consulta() -> None:
    redemption = _redemption()
    voucher = Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    client = _client()
    client.id = redemption.cliente_id
    business = Negocio(
        id=voucher.negocio_id,
        nombre="Café Central",
        tipo=TipoNegocio.SOCIO,
    )
    result = MagicMock()
    result.one_or_none.return_value = (
        redemption,
        client,
        None,
        voucher,
        None,
        business,
    )
    session = _session()
    session.execute.return_value = result

    detail = await CanjeService.get(
        session,
        redemption.id,
        redemption.cliente_id,
        Role.CLIENTE,
        None,
    )

    assert detail.canje.id == redemption.id
    assert detail.usuario_cliente.id == client.id
    assert detail.usuario_cajero_socio is None
    assert detail.vale.id == voucher.id
    assert detail.sucursal is None
    assert detail.negocio.id == business.id
    session.execute.assert_awaited_once()
    assert "JOIN" in str(session.execute.await_args.args[0].compile())


@pytest.mark.asyncio
async def test_get_audit_reutiliza_consulta_de_detalle() -> None:
    redemption = _redemption()
    client = _client()
    client.id = redemption.cliente_id
    voucher = Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    business = Negocio(
        id=voucher.negocio_id,
        nombre="Café Central",
        tipo=TipoNegocio.SOCIO,
    )
    session = _session()

    with patch.object(
        CanjeService,
        "_get_detail_records",
        new=AsyncMock(
            return_value=(redemption, client, None, voucher, None, business)
        ),
    ) as get_records:
        detail = await CanjeService.get_audit(
            session,
            redemption.id,
            uuid4(),
            Role.ADMIN,
            None,
        )

    assert detail.canje.id == redemption.id
    assert detail.usuario_cliente.id == client.id
    assert detail.usuario_cajero_socio is None
    assert detail.sucursal is None
    assert detail.negocio.id == business.id
    get_records.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_copia_vale_descuenta_puntos_y_registra_movimiento() -> None:
    session = _session()
    client = _client(points=700)
    business_id = uuid4()
    voucher = Vale(
        total_costo=Decimal("50.00"),
        total_puntos=500,
        nombre="Vale Bs 50",
        categoria_id=uuid4(),
        negocio_id=business_id,
    )
    config = ConfigPuntos(
        start_date=datetime.now(timezone.utc),
        asignacion_bolivianos=100,
        asignacion_puntos=10,
        costo_vale_bolivianos=50,
        costo_vale_puntos=500,
    )

    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
        patch.object(UserService, "get", new=AsyncMock(return_value=client)),
        patch.object(
            ConfigPuntosService,
            "get_active",
            new=AsyncMock(return_value=config),
        ),
        patch.object(
            CanjeService,
            "_generate_unique_code",
            new=AsyncMock(return_value="00123456"),
        ),
    ):
        redemption = await CanjeService.create(
            session,
            CanjeCreate(vale_id=voucher.id, referencia=None),
            client.id,
            Role.CLIENTE,
        )

    assert redemption.status is EstadoCanje.PENDIENTE
    assert redemption.codigo_canje == "00123456"
    assert redemption.dador_id is None
    assert redemption.sucursal_id is None
    assert redemption.total_puntos == voucher.total_puntos
    assert redemption.total_costo == voucher.total_costo
    assert client.puntos == 200
    assert redemption.expires_at - redemption.created_at == timedelta(days=30)
    assert session.add.call_args_list[0].args[0] is redemption
    movements = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], MovimientoPuntos)
    ]
    assert len(movements) == 1
    assert movements[0].tipo_movimiento is TipoMovimiento.CANJE
    assert movements[0].canje_id == redemption.id
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_rechaza_saldo_insuficiente() -> None:
    session = _session()
    client = _client(points=499)
    voucher = Vale(
        total_costo=Decimal("50.00"),
        total_puntos=500,
        nombre="Vale",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )

    with (
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
        patch.object(UserService, "get", new=AsyncMock(return_value=client)),
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.create(
                session,
                CanjeCreate(vale_id=voucher.id, referencia=""),
                client.id,
                Role.CLIENTE,
            )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_expire_pending_actualiza_vencidos_en_lote() -> None:
    session = _session()
    actor_id = uuid4()
    result = MagicMock()
    result.rowcount = 4
    session.execute.return_value = result

    response = await CanjeService.expire_pending(session, actor_id)

    assert response.expired_count == 4
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    assert EstadoCanje.PENDIENTE in compiled.params.values()
    assert EstadoCanje.EXPIRADO in compiled.params.values()
    assert actor_id in compiled.params.values()


@pytest.mark.asyncio
async def test_generate_unique_code_conserva_ocho_digitos() -> None:
    session = _session()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    with patch("app.domains.canje.services.secrets.randbelow", return_value=123):
        code = await CanjeService._generate_unique_code(session)

    assert code == "00000123"


@pytest.mark.asyncio
async def test_redeem_confirma_sin_modificar_saldo_ni_registrar_movimiento() -> None:
    session = _session()
    client = _client(points=700)
    branch_id = uuid4()
    actor_id = uuid4()
    business_id = uuid4()
    branch = Sucursal(nombre="Central", negocio_id=business_id)
    branch.id = branch_id
    redemption = _redemption(
        cliente_id=client.id,
    )
    voucher = Vale(
        total_costo=Decimal("50.00"),
        total_puntos=500,
        nombre="Vale",
        categoria_id=uuid4(),
        negocio_id=business_id,
    )
    voucher.id = redemption.vale_id
    result = MagicMock()
    result.scalar_one_or_none.return_value = redemption
    session.execute.return_value = result

    with (
        patch.object(
            SucursalService,
            "get",
            new=AsyncMock(return_value=branch),
        ),
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
    ):
        redeemed = await CanjeService.redeem(
            session,
            redemption.codigo_canje,
            actor_id,
            Role.CAJERO,
            branch_id,
        )

    assert redeemed.status is EstadoCanje.CANJEADO
    assert redeemed.dador_id == actor_id
    assert redeemed.sucursal_id == branch_id
    assert client.puntos == 700
    movements = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], MovimientoPuntos)
    ]
    assert movements == []
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_redeem_marca_codigo_expirado_sin_descontar() -> None:
    session = _session()
    redemption = _redemption(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = redemption
    session.execute.return_value = result

    with pytest.raises(AppException) as error:
        await CanjeService.redeem(
            session,
            redemption.codigo_canje,
            uuid4(),
            Role.SOCIO,
            uuid4(),
        )

    assert error.value.status_code == 409
    assert redemption.status is EstadoCanje.EXPIRADO
    session.commit.assert_awaited_once()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_redeem_rechaza_sucursal_de_otro_negocio() -> None:
    session = _session()
    redemption = _redemption()
    branch = Sucursal(nombre="Otra", negocio_id=uuid4())
    voucher = Vale(
        total_costo=Decimal("50.00"),
        total_puntos=500,
        nombre="Vale",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )
    voucher.id = redemption.vale_id
    result = MagicMock()
    result.scalar_one_or_none.return_value = redemption
    session.execute.return_value = result

    with (
        patch.object(
            SucursalService,
            "get",
            new=AsyncMock(return_value=branch),
        ),
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.redeem(
                session,
                redemption.codigo_canje,
                uuid4(),
                Role.CAJERO,
                branch.id,
            )

    assert error.value.status_code == 422
    assert redemption.dador_id is None
    assert redemption.sucursal_id is None
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "role",
    [Role.SUPERADMIN, Role.OWNER, Role.ADMIN, Role.CAJERO, Role.SOCIO],
)
@pytest.mark.asyncio
async def test_cancel_permite_roles_autorizados_en_canje_pendiente(
    role: Role,
) -> None:
    session = _session()
    actor_id = uuid4()
    redemption = _redemption()
    client = _client(points=200)
    client.id = redemption.cliente_id
    business_id = uuid4()
    branch = Sucursal(nombre="Central", negocio_id=business_id)
    voucher = Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale",
        categoria_id=uuid4(),
        negocio_id=business_id,
    )
    movement = MovimientoPuntos(
        usuario_id=client.id,
        tipo_movimiento=TipoMovimiento.CANJE,
        puntos=redemption.total_puntos,
        operacion_id=None,
        canje_id=redemption.id,
    )

    with (
        patch.object(
            CanjeService,
            "_get_raw",
            new=AsyncMock(return_value=redemption),
        ),
        patch.object(
            MovimientoPuntosService,
            "get_by_redemption_id",
            new=AsyncMock(return_value=movement),
        ),
        patch.object(UserService, "get", new=AsyncMock(return_value=client)),
        patch.object(SucursalService, "get", new=AsyncMock(return_value=branch)),
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
    ):
        cancelled = await CanjeService.cancel(
            session,
            redemption.id,
            actor_id,
            role,
            branch.id if role in {Role.CAJERO, Role.SOCIO} else None,
        )

    assert cancelled.status is EstadoCanje.CANCELADO
    assert client.puntos == 700
    assert client.updated_by == actor_id
    assert movement.is_deleted is False
    adjustments = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], MovimientoPuntos)
    ]
    assert len(adjustments) == 1
    assert adjustments[0].tipo_movimiento is TipoMovimiento.AJUSTE
    assert adjustments[0].movimiento_origen_id == movement.id
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_rechaza_operador_de_otro_negocio() -> None:
    session = _session()
    redemption = _redemption()
    branch = Sucursal(nombre="Central", negocio_id=uuid4())
    voucher = Vale(
        id=redemption.vale_id,
        total_costo=redemption.total_costo,
        total_puntos=redemption.total_puntos,
        nombre="Vale aliado",
        categoria_id=uuid4(),
        negocio_id=uuid4(),
    )

    with (
        patch.object(
            CanjeService,
            "_get_raw",
            new=AsyncMock(return_value=redemption),
        ),
        patch.object(
            SucursalService,
            "get",
            new=AsyncMock(return_value=branch),
        ),
        patch.object(ValeService, "get", new=AsyncMock(return_value=voucher)),
        patch.object(
            MovimientoPuntosService,
            "get_by_redemption_id",
            new=AsyncMock(),
        ) as get_movement,
        patch.object(UserService, "get", new=AsyncMock()) as get_user,
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.cancel(
                session,
                redemption.id,
                uuid4(),
                Role.CAJERO,
                branch.id,
            )

    assert error.value.status_code == 403
    assert error.value.code == "PERMISSION_DENIED"
    assert redemption.status is EstadoCanje.PENDIENTE
    get_movement.assert_not_awaited()
    get_user.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_rechaza_operador_sin_sucursal() -> None:
    session = _session()
    redemption = _redemption()

    with (
        patch.object(
            CanjeService,
            "_get_raw",
            new=AsyncMock(return_value=redemption),
        ),
        patch.object(SucursalService, "get", new=AsyncMock()) as get_branch,
        patch.object(ValeService, "get", new=AsyncMock()) as get_voucher,
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.cancel(
                session,
                redemption.id,
                uuid4(),
                Role.SOCIO,
                None,
            )

    assert error.value.status_code == 403
    get_branch.assert_not_awaited()
    get_voucher.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_sin_movimiento_previo_tambien_repone_puntos() -> None:
    session = _session()
    redemption = _redemption()
    client = _client(points=200)
    client.id = redemption.cliente_id

    with (
        patch.object(
            CanjeService,
            "_get_raw",
            new=AsyncMock(return_value=redemption),
        ),
        patch.object(
            MovimientoPuntosService,
            "get_by_redemption_id",
            new=AsyncMock(return_value=None),
        ),
        patch.object(UserService, "get", new=AsyncMock(return_value=client)),
    ):
        cancelled = await CanjeService.cancel(
            session,
            redemption.id,
            uuid4(),
            Role.ADMIN,
            None,
        )

    assert cancelled.status is EstadoCanje.CANCELADO
    assert client.puntos == 700
    adjustment = session.add.call_args.args[0]
    assert adjustment.tipo_movimiento is TipoMovimiento.AJUSTE
    assert adjustment.movimiento_origen_id is None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_rechaza_cliente_aunque_sea_propietario() -> None:
    session = _session()
    client_id = uuid4()
    redemption = _redemption(cliente_id=client_id)

    with patch.object(
        CanjeService,
        "_get_raw",
        new=AsyncMock(return_value=redemption),
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.cancel(
                session,
                redemption.id,
                client_id,
                Role.CLIENTE,
                None,
            )

    assert error.value.status_code == 403
    assert redemption.status is EstadoCanje.PENDIENTE
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_detecta_expiracion_sin_registrar_movimiento() -> None:
    session = _session()
    redemption = _redemption(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    with patch.object(
        CanjeService,
        "_get_raw",
        new=AsyncMock(return_value=redemption),
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.cancel(
                session,
                redemption.id,
                uuid4(),
                Role.ADMIN,
                None,
            )

    assert error.value.status_code == 409
    assert redemption.status is EstadoCanje.EXPIRADO
    session.add.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "redemption_status",
    [EstadoCanje.CANJEADO, EstadoCanje.EXPIRADO, EstadoCanje.CANCELADO],
)
@pytest.mark.asyncio
async def test_cancel_rechaza_canje_que_no_este_pendiente(
    redemption_status: EstadoCanje,
) -> None:
    session = _session()
    redemption = _redemption(status=redemption_status)

    with patch.object(
        CanjeService,
        "_get_raw",
        new=AsyncMock(return_value=redemption),
    ):
        with pytest.raises(AppException) as error:
            await CanjeService.cancel(
                session,
                redemption.id,
                uuid4(),
                Role.ADMIN,
                None,
            )

    assert error.value.status_code == 409
    session.commit.assert_not_awaited()
