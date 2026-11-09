from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.reportes.schemas import ReportePuntosQuery
from app.domains.reportes.services import ReporteService
from app.middlewares.limiter import limiter
from app.shared.enums import Role
from app.shared.schemas.errors import ErrorResponse


router = APIRouter(prefix="/reportes", tags=["Reportes"])

ERROR_RESPONSES = {
    code: {"model": ErrorResponse} for code in (401, 403, 422, 429, 500)
}


def _error_responses(*codes: int) -> dict[int, dict[str, object]]:
    return {code: ERROR_RESPONSES[code] for code in codes}


@router.get(
    "/puntos",
    response_class=Response,
    summary="Descargar reporte de puntos en Excel",
    description=(
        "Genera un archivo .xlsx con los puntos asignados o canjeados en el "
        "periodo indicado. La hoja 'Por sucursal' contiene una fila por día "
        "con cantidad, puntos y bolivianos por sucursal y del sistema. La hoja "
        "'Por usuario' contiene los totales del periodo por usuario, ordenados "
        "de mayor a menor en bolivianos."
    ),
    responses={
        200: {
            "description": "Archivo Excel del reporte.",
            "content": {ReporteService.XLSX_MEDIA_TYPE: {}},
        },
        **_error_responses(401, 403, 422, 429, 500),
    },
)
@limiter.limit("10/minute")
async def get_reporte_puntos(
    request: Request,
    query: Annotated[ReportePuntosQuery, Query()],
    current_user: Annotated[
        CurrentUser,
        Depends(require_role(Role.SUPERADMIN, Role.OWNER, Role.ADMIN)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    content = await ReporteService.generar_excel_puntos(db_session, query, settings)
    return Response(
        content=content,
        media_type=ReporteService.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ReporteService.nombre_archivo(query)}"'
            )
        },
    )
