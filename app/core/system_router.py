from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.core.database import check_database_connection
from app.core.config import Settings, get_settings




router = APIRouter()

@router.get("/", include_in_schema=False)
async def root(settings: Settings = Depends(get_settings),):
    """Redirige automáticamente a la documentación interactiva en desarrollo"""
    if settings.DEBUG:
        return RedirectResponse(url="/docs")
    return {"message": "Svelpy API", "status": "active"}


@router.get("/health", tags=["Health"],)
async def health_check(request: Request,response: Response,settings: Settings = Depends(get_settings),):
    """
    Endpoint de salud operativa (Readiness Probe).
    Verifica que la base de datos responda antes de retornar 200.
    """
    
    try:
        database_engine = getattr(request.app.state, "database", None)
        if database_engine is None:
            raise RuntimeError("Base de datos no inicializada")
        
        await check_database_connection(database_engine)
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "database": "connected"
        }
            
    except Exception as error:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "error",
                "message": "Servicio no disponible temporalmente.",
                "details": {
                    "app": settings.APP_NAME,
                    "version": settings.APP_VERSION,
                    "database": "disconnected",
                    "reason": str(error),
                },
            }
