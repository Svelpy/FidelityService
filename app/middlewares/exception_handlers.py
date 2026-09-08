import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings
from app.shared.errors.exceptions import AppException
from app.domains.error_logs import ErrorLog


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    """Registra los interceptores globales de errores en la app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request,exc: AppException,) -> JSONResponse:
        headers = {}
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "fail",
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request,exc: RequestValidationError) -> JSONResponse:
        errors_details = {
            " -> ".join(str(x) for x in error["loc"][1:])
            if len(error["loc"]) > 1
            else str(error["loc"][0]): error["msg"]
            for error in exc.errors()
        }

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "fail",
                "code": "VALIDATION_ERROR",
                "message": "Los datos enviados no son válidos.",
                "details": errors_details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request,exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "fail",
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": {},
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request,exc: Exception) -> JSONResponse:
        stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        if settings.DEBUG:
            logger.error("Error crítico detectado: %s\n%s", exc, stack_trace)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                    "details": {"stack": stack_trace},
                },
            )

        try:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            user_id = None
            if hasattr(request.state, "user"):
                user_id = str(request.state.user.id)

            log = ErrorLog(
                status="error",
                message=str(exc),
                stack=stack_trace,
                path=request.url.path,
                method=request.method,
                ip_address=ip_address,
                user_agent=user_agent,
                user_id=user_id,
            )
            await log.insert()
        except Exception as db_error:
            logger.error("Error al intentar guardar log en MongoDB: %s", db_error)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Ocurrió un error interno.",
                "details": {},
            },
        )
