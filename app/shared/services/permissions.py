"""
shared/services/permissions.py

Única fuente de verdad de "quién puede hacer qué, sobre qué módulo".
Si agregás un rol o un módulo nuevo, TODO el cambio pasa por este
archivo — no se tocan las rutas.

Los conjuntos de acciones son `frozenset` para que sean inmutables.
`frozenset()` vacío indica que el rol no tiene ninguna acción sobre ese
módulo. Un módulo ausente también equivale a sin acceso.
"""

from app.shared.enums import Action, Module, Role


ROLE_PERMISSIONS: dict[Role, dict[Module, frozenset[Action]]] = {
    Role.SUPERADMIN: {
        Module.CANJE: frozenset({Action.READ, Action.AUDIT}),  # no existe delete
        Module.CATEGORIA: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.CONFIG_PUNTOS: frozenset({Action.CREATE, Action.READ, Action.AUDIT}),  # no existe delete ni update
        Module.MOVIMIENTOS_PUNTOS: frozenset({Action.READ, Action.AUDIT}),  # no existe create, update, delete
        Module.NEGOCIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.OPERACION: frozenset({Action.READ, Action.AUDIT}),  # no existe delete ni update
        Module.SUCURSAL: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.VALE: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
    },
    Role.OWNER: {
        Module.CANJE: frozenset({Action.READ}),  # no existe delete
        Module.CATEGORIA: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.CONFIG_PUNTOS: frozenset({Action.CREATE, Action.READ}),  # no existe delete ni update
        Module.MOVIMIENTOS_PUNTOS: frozenset({Action.READ}),  # no existe create, update, delete
        Module.NEGOCIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.OPERACION: frozenset({Action.READ}),  # no existe delete ni update
        Module.SUCURSAL: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.VALE: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
    },
    Role.ADMIN: {
        Module.CANJE: frozenset({Action.READ, Action.UPDATE}),  # no existe delete
        Module.CATEGORIA: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.CONFIG_PUNTOS: frozenset({Action.CREATE, Action.READ}),  # no existe delete ni update
        Module.MOVIMIENTOS_PUNTOS: frozenset({Action.READ}),  # no existe create, update, delete
        Module.NEGOCIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.OPERACION: frozenset({Action.CREATE, Action.READ}),  # no existe delete ni update
        Module.SUCURSAL: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
        Module.VALE: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),
    },
    Role.CAJERO: {
        Module.CANJE: frozenset({Action.READ, Action.UPDATE}),  # se usa
        Module.CATEGORIA: frozenset({Action.READ}),  # se usa en list category, yo lo quitaria
        Module.CONFIG_PUNTOS: frozenset({Action.READ}),  # se usa para mostrar la actual
        Module.MOVIMIENTOS_PUNTOS: frozenset({Action.READ}),  # para revisar URGENTE
        Module.NEGOCIO: frozenset({Action.READ}),  # se usa en los filtros de operacion
        Module.OPERACION: frozenset({Action.CREATE, Action.READ}),  # se usa
        Module.SUCURSAL: frozenset(),  # no se usa
        Module.USUARIO: frozenset(),  # 
        Module.VALE: frozenset({Action.READ}),  # se usa en list vale, pero yo lo quitaria
    },
    Role.CLIENTE: {
        Module.CANJE: frozenset({Action.CREATE}),  # get me canjes no requiere Action.READ
        Module.CATEGORIA: frozenset({Action.READ}),  # se usa
        Module.CONFIG_PUNTOS: frozenset(),  # no usa
        Module.MOVIMIENTOS_PUNTOS: frozenset(),  # get me movimientos puntos no requiere Action.READ
        Module.NEGOCIO: frozenset({Action.READ}),  # solicitud del frontend para renderizar logos de negocios asociados
        Module.OPERACION: frozenset(),  # no usa
        Module.SUCURSAL: frozenset(),  # no usa
        Module.USUARIO: frozenset(),  # get me usuario no requiere Action.READ
        Module.VALE: frozenset({Action.READ}),  # se usa
    },
    Role.SOCIO: {
        Module.CANJE: frozenset({Action.READ, Action.UPDATE}),  # read para listar y get by codigo, update para redeem
        Module.CATEGORIA: frozenset(),
        Module.CONFIG_PUNTOS: frozenset(),
        Module.MOVIMIENTOS_PUNTOS: frozenset(),
        Module.NEGOCIO: frozenset(),
        Module.OPERACION: frozenset(),
        Module.SUCURSAL: frozenset(),
        Module.USUARIO: frozenset(),
        Module.VALE: frozenset(),
    },
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, frozenset())
