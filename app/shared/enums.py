from enum import Enum

class Role(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    OWNER = "OWNER"
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


class EstadoConfigPuntos(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class EstadoCanje(str, Enum):
    PENDIENTE = "PENDIENTE"
    CANJEADO = "CANJEADO"
    EXPIRADO = "EXPIRADO"
    CANCELADO = "CANCELADO"


class TipoMovimiento(str, Enum):
    ACUMULA = "ACUMULA" #OPERACION (SUMA)
    CANJE = "CANJE"     #CANJE (RESTA)
    AJUSTE = "AJUSTE"   #CANCELACION DE CANJE (SUMA)


class Genero(str, Enum):
    M = "M"
    F = "F"
    O = "O"

    
