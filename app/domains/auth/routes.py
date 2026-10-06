from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.schemas import (
    UserLogin,
    TokenResponse,
)
from app.domains.auth.services import AuthService
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.errors import ErrorResponse
from app.middlewares.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])

WWW_AUTHENTICATE_HEADER = {
    "description": "Indica que el cliente debe autenticarse con Bearer.",
    "schema": {"type": "string", "example": "Bearer"},
}

RETRY_AFTER_HEADER = {
    "description": "Segundos mínimos antes de volver a intentar la solicitud.",
    "schema": {"type": "integer", "example": 30},
}

SET_COOKIE_HEADER = {
    "description": (
        "Cookie HttpOnly refresh_token establecida o eliminada por el "
        "backend. El navegador la gestiona automáticamente."
    ),
    "schema": {"type": "string"},
}

CACHE_CONTROL_HEADER = {
    "description": "La respuesta no debe almacenarse en caché.",
    "schema": {"type": "string", "example": "no-store"},
}

COMMON_ERROR_RESPONSES = {
    422: {
        "model": ErrorResponse,
        "description": "Los datos enviados no son válidos.",
    },
    429: {
        "model": ErrorResponse,
        "description": "Se superó el límite de solicitudes. Revisar Retry-After.",
        "headers": {"Retry-After": RETRY_AFTER_HEADER},
    },
    500: {
        "model": ErrorResponse,
        "description": "Error interno; el frontend debe mostrar un mensaje genérico.",
    },
    503: {
        "model": ErrorResponse,
        "description": "Servicio temporalmente no disponible.",
    },
}

LOGIN_ERROR_RESPONSES = {
    **COMMON_ERROR_RESPONSES,
    401: {
        "model": ErrorResponse,
        "description": "Email o contraseña incorrectos.",
        "headers": {"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
    },
}

REFRESH_ERROR_RESPONSES = {
    **COMMON_ERROR_RESPONSES,
    401: {
        "model": ErrorResponse,
        "description": "El refresh token es requerido, inválido, expiró o fue reutilizado.",
        "headers": {"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
    },
    403: {
        "model": ErrorResponse,
        "description": "El header X-CSRF-Token es inválido.",
    },
}

LOGOUT_ERROR_RESPONSES = {
    **COMMON_ERROR_RESPONSES,
    403: {
        "model": ErrorResponse,
        "description": "El header X-CSRF-Token es inválido.",
    },
}

TOKEN_SUCCESS_RESPONSES = {
    200: {
        "description": "Tokens emitidos y cookie refresh_token establecida.",
        "headers": {
            "Set-Cookie": SET_COOKIE_HEADER,
            "Cache-Control": CACHE_CONTROL_HEADER,
        },
    }
}

LOGOUT_SUCCESS_RESPONSES = {
    204: {
        "description": "Sesión revocada y cookie refresh_token eliminada.",
        "headers": {"Set-Cookie": SET_COOKIE_HEADER},
    }
}

COOKIE_OPENAPI = {
    "parameters": [
        {
            "name": "refresh_token",
            "in": "cookie",
            "required": False,
            "description": (
                "Cookie HttpOnly administrada por el navegador. El frontend "
                "no debe leerla ni enviarla manualmente."
            ),
            "schema": {"type": "string"},
        }
    ]
}

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Recibe username como el email y password mediante "
        "application/x-www-form-urlencoded. Devuelve el access token y "
        "csrf_token; además establece la cookie HttpOnly refresh_token."
    ),
    responses={**TOKEN_SUCCESS_RESPONSES, **LOGIN_ERROR_RESPONSES},
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """
    Iniciar sesión con correo y contraseña.
    
    Emite un token JWT de acceso válido.
    """
    try:
        credentials = UserLogin(email=form_data.username,password=form_data.password)
    except ValidationError as error:
        raise AppException(
            "Los datos enviados no son válidos.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.VALIDATION_ERROR,
            {"username": error.errors()[0]["msg"]},
        ) from error

    tokens = await AuthService.login(db_session, credentials, settings)
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=tokens.access_token,
        csrf_token=tokens.csrf_token,
        token_type="bearer",
    )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
    description=(
        "Usa automáticamente la cookie HttpOnly refresh_token y requiere "
        "X-CSRF-Token cuando existe una sesión. El frontend debe enviar "
        "credentials: include y reemplazar el csrf_token recibido. La cookie "
        "se rota después de un refresh exitoso."
    ),
    responses={**TOKEN_SUCCESS_RESPONSES, **REFRESH_ERROR_RESPONSES},
    openapi_extra=COOKIE_OPENAPI,
)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_token: Annotated[str | None,Header(alias="X-CSRF-Token")] = None,
) -> TokenResponse:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    tokens = await AuthService.refresh(
        db_session=db_session,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
        settings=settings,
    )

    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )

    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=tokens.access_token,
        csrf_token=tokens.csrf_token,
        token_type="bearer",
    )

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
    description=(
        "Revoca la sesión asociada a la cookie HttpOnly refresh_token. El "
        "frontend debe enviar credentials: include y X-CSRF-Token cuando "
        "existe una sesión. El access token ya emitido continúa válido hasta "
        "su expiración."
    ),
    responses={**LOGOUT_SUCCESS_RESPONSES, **LOGOUT_ERROR_RESPONSES},
    openapi_extra=COOKIE_OPENAPI,
)
@limiter.limit("10/minute")
async def logout(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_token: Annotated[str | None,Header(alias="X-CSRF-Token")] = None,
) -> None:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    await AuthService.logout(
        db_session=db_session,
        refresh_token=refresh_token,
        csrf_token=csrf_token,
        settings=settings,
    )

    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/api/v1/auth",
    )



