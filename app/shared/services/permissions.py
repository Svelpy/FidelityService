"""
shared/services/permissions.py

Única fuente de verdad de "quién puede hacer qué, sobre qué módulo".
Si agregás un rol o un módulo nuevo, TODO el cambio pasa por este
archivo — no se tocan las rutas.
"""

from app.shared.enums import Role, Module, Action


ALL_ACTIONS = {Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}
SIN_ELIMINAR = {Action.CREATE, Action.READ, Action.UPDATE}
SIN_ELIMINAR_SIN_CREAR = {Action.READ, Action.UPDATE}
SOLO_LECTURA = {Action.READ}

# dict[Role, dict[Module, set[Action]]]
# Un módulo ausente en el dict de un rol == sin acceso a ese módulo
# (ni siquiera lectura).
ROLE_PERMISSIONS: dict[Role, dict[Module, set[Action]]] = {
    Role.SUPERADMIN: {
        **{module: ALL_ACTIONS for module in Module},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.OWNER: {
        **{module: ALL_ACTIONS for module in Module},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.ADMIN: {
        **{module: ALL_ACTIONS for module in Module},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.CAJERO: {
        Module.CANJE: {Action.READ, Action.UPDATE},#se usa
        Module.CATEGORIA: SOLO_LECTURA,#se usa en list category,yo lo quitaria
        Module.CONFIG_PUNTOS: SOLO_LECTURA,#se usa para mostrar la actual
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA, # para revisar URGENTE
        Module.NEGOCIO: SOLO_LECTURA,# se usa en los filtros de operacio
        Module.OPERACION: {Action.CREATE, Action.READ},#se usa
        Module.SUCURSAL: {},#no se usa
        Module.USUARIO: SOLO_LECTURA,#se usa en get by ci
        Module.VALE: SOLO_LECTURA,#se usa en list vale, pero yo lo quitaria
    },
    Role.CLIENTE: {
        Module.CANJE: {Action.CREATE},#get me canjes no reguiere Action.READ
        Module.CATEGORIA: SOLO_LECTURA,#se usa
        Module.CONFIG_PUNTOS: {},#no usa
        Module.MOVIMIENTOS_PUNTOS: {},#get me movimientos puntos no reguiere Action.READ
        Module.NEGOCIO: SOLO_LECTURA,#Solicitud del frontend para renderizar logos de negocios asociados
        Module.OPERACION: {},#no usa
        Module.SUCURSAL: {},#no usa
        Module.USUARIO: {},#get me usuario no reguiere action.READ
        Module.VALE: SOLO_LECTURA,#se usa
    },
    Role.SOCIO: {
        Module.CANJE: {Action.READ, Action.UPDATE},
        #read para listar y get by codigo, patch para redeem
        Module.CATEGORIA: {},
        Module.CONFIG_PUNTOS: {},
        Module.MOVIMIENTOS_PUNTOS: {},
        Module.NEGOCIO: {},
        Module.OPERACION: {},
        Module.SUCURSAL: {},
        Module.USUARIO: {},
        Module.VALE: {},
    },
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, set())
