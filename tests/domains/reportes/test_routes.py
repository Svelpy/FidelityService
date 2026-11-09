from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.reportes.routes import router
from app.domains.reportes.services import ReporteService
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Role, TipoReportePuntos


URL = "/reportes/puntos?fecha_inicio=2026-11-01&fecha_fin=2026-11-30&tipo=ASIGNADOS"


@pytest.fixture
def route_context() -> Generator[tuple[TestClient, CurrentUser, MagicMock, MagicMock], None, None]:
    app = FastAPI()
    register_exception_handlers(app, get_settings())
    app.include_router(router)

    current_user = CurrentUser(id=uuid4(), role=Role.ADMIN, sucursal_id=uuid4())
    db_session = MagicMock(spec=AsyncSession)
    settings = MagicMock(spec=Settings)

    async def override_principal() -> CurrentUser:
        return current_user

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        yield client, current_user, db_session, settings


@pytest.mark.parametrize("actor_role", [Role.SUPERADMIN, Role.OWNER, Role.ADMIN])
def test_reporte_puntos_devuelve_excel(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, db_session, settings = route_context
    current_user.role = actor_role

    with patch.object(
        ReporteService,
        "generar_excel_puntos",
        new=AsyncMock(return_value=b"xlsx"),
    ) as service:
        response = client.get(URL)

    assert response.status_code == 200
    assert response.content == b"xlsx"
    assert response.headers["content-type"] == ReporteService.XLSX_MEDIA_TYPE
    assert response.headers["content-disposition"] == (
        'attachment; filename="reporte_puntos_asignados_2026-11-01_2026-11-30.xlsx"'
    )
    args = service.await_args.args
    assert args[0] is db_session
    assert args[1].tipo is TipoReportePuntos.ASIGNADOS
    assert args[2] is settings


@pytest.mark.parametrize("actor_role", [Role.CAJERO, Role.SOCIO, Role.CLIENTE])
def test_reporte_puntos_rechaza_roles_no_autorizados(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    actor_role: Role,
) -> None:
    client, current_user, _, _ = route_context
    current_user.role = actor_role

    with patch.object(ReporteService, "generar_excel_puntos", new=AsyncMock()) as service:
        response = client.get(URL)

    assert response.status_code == 403
    service.assert_not_awaited()


@pytest.mark.parametrize(
    "params",
    [
        "fecha_inicio=2026-11-30&fecha_fin=2026-11-01&tipo=ASIGNADOS",
        "fecha_inicio=2026-01-01&fecha_fin=2027-06-01&tipo=ASIGNADOS",
        "fecha_inicio=2026-11-01&fecha_fin=2026-11-30&tipo=OTRO",
        "fecha_inicio=2026-11-01&tipo=ASIGNADOS",
        "fecha_inicio=2026-11-01&fecha_fin=2026-11-30&tipo=ASIGNADOS&sucursal_id=x",
    ],
)
def test_reporte_puntos_valida_parametros(
    route_context: tuple[TestClient, CurrentUser, MagicMock, MagicMock],
    params: str,
) -> None:
    client, _, _, _ = route_context

    with patch.object(ReporteService, "generar_excel_puntos", new=AsyncMock()) as service:
        response = client.get(f"/reportes/puntos?{params}")

    assert response.status_code == 422
    service.assert_not_awaited()
