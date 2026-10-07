from enum import Enum

class Role(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    CAJERO = "CAJERO"
    CLIENTE = "CLIENTE"
    SOCIO = "SOCIO"


class Module(str, Enum):
    CATEGORIA = "CATEGORIA"
    NEGOCIO = "NEGOCIO"
    SUCURSAL = "SUCURSAL"
    USUARIO = "USUARIO"
    CANJE = "CANJE"
    OPERACION = "OPERACION"
    CONFIG_PUNTOS = "CONFIG_PUNTOS"
    MOVIMIENTOS_PUNTOS = "MOVIMIENTOS_PUNTOS"
    VALE = "VALE"


class Action(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class TipoNegocio(str, Enum):
    MAIN = "MAIN"
    SOCIO = "SOCIO"


class EstadoCanje(str, Enum):
    PENDIENTE = "PENDIENTE"
    CANJEADO = "CANJEADO"
    EXPIRADO = "EXPIRADO"
    CANCELADO = "CANCELADO"


class TipoMovimiento(str, Enum):
    ACUMULA = "ACUMULA"
    CANJE = "CANJE"
    AJUSTE = "AJUSTE"
    EXPIRA = "EXPIRA"

class Genero(str, Enum):
    M = "M"
    F = "F"
    O = "O"
    
    