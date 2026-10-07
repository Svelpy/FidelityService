"""Importa todos los modelos persistentes para registrar su metadata."""

from app.domains.auth.models import AuthSession
from app.domains.canje.models import Canje
from app.domains.categoria.models import Categoria
from app.domains.config_puntos.models import ConfigPuntos
from app.domains.error_logs.models import ErrorLog
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.vale.models import Vale

__all__ = [
    "AuthSession",
    "Canje",
    "Categoria",
    "ConfigPuntos",
    "ErrorLog",
    "MovimientoPuntos",
    "Negocio",
    "Operacion",
    "Sucursal",
    "User",
    "Vale",
]
