from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.reportes.schemas import ReportePuntosQuery, RuletaResponse
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


@router.get(
    "/clientes",
    response_class=Response,
    summary="Descargar clientes activos en Excel",
    description=(
        "Genera un archivo .xlsx con todos los usuarios CLIENTE que no están "
        "eliminados, ordenados por nombre: datos de contacto, puntos actuales, "
        "nivel y fecha de registro (hora local)."
    ),
    responses={
        200: {
            "description": "Archivo Excel con los clientes.",
            "content": {ReporteService.XLSX_MEDIA_TYPE: {}},
        },
        **_error_responses(401, 403, 429, 500),
    },
)
@limiter.limit("10/minute")
async def get_reporte_clientes(
    request: Request,
    current_user: Annotated[
        CurrentUser,
        Depends(require_role(Role.SUPERADMIN, Role.OWNER, Role.ADMIN)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    content = await ReporteService.generar_excel_clientes(db_session, settings)
    nombre = ReporteService.nombre_archivo_clientes(settings)
    return Response(
        content=content,
        media_type=ReporteService.XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get(
    "/clientes/ruleta",
    response_class=JSONResponse,
    summary="Descargar ruleta de clientes en JSON",
    description=(
        "Genera directamente desde la base de datos el archivo .json de la "
        "ruleta con todos los clientes activos: label = 'Nombre Apellidos' y "
        "weight = Peso (1 por cada 50 puntos completos; 50, 51 o 70 puntos "
        "valen 1). Los clientes con menos de 50 puntos no participan. Devuelve "
        "422 si ningún cliente tiene al menos 50 puntos."
    ),
    responses={
        200: {
            "description": "Archivo JSON de la ruleta.",
            "content": {"application/json": {"schema": RuletaResponse.model_json_schema(by_alias=True)}},
        },
        **_error_responses(401, 403, 422, 429, 500),
    },
)
@limiter.limit("10/minute")
async def get_ruleta_clientes(
    request: Request,
    current_user: Annotated[
        CurrentUser,
        Depends(require_role(Role.SUPERADMIN, Role.OWNER, Role.ADMIN)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    ruleta = await ReporteService.generar_ruleta_clientes(db_session)
    nombre = ReporteService.nombre_archivo_ruleta(settings)
    return JSONResponse(
        content=ruleta.model_dump(mode="json", by_alias=True),
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
