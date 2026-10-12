from fastapi import APIRouter

from app.core.system_router import router as system_router
from app.domains.auth.routes import router as auth_router
from app.domains.categoria.routes import router as categoria_router
from app.domains.config_puntos.routes import router as config_puntos_router
from app.domains.negocio.routes import router as negocio_router
from app.domains.sucursal.routes import router as sucursal_router
from app.domains.users.routes import router as users_router
from app.domains.vale.routes import router as vale_router

no_system_router = APIRouter(prefix="/api/v1")
no_system_router.include_router(auth_router)
no_system_router.include_router(users_router)
no_system_router.include_router(categoria_router)
no_system_router.include_router(config_puntos_router)
no_system_router.include_router(negocio_router)
no_system_router.include_router(sucursal_router)
no_system_router.include_router(vale_router)


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(no_system_router)
