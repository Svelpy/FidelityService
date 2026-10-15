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
    Role.ADMIN: {
        **{module: SIN_ELIMINAR for module in Module},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.CAJERO: {
        Module.CATEGORIA: SOLO_LECTURA,
        Module.NEGOCIO: SOLO_LECTURA,
        Module.SUCURSAL: SOLO_LECTURA,
        Module.USUARIO: SIN_ELIMINAR,
        Module.CANJE: {Action.READ, Action.UPDATE},
        Module.OPERACION: {Action.CREATE, Action.READ},
        Module.CONFIG_PUNTOS: SOLO_LECTURA,
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
        Module.VALE: SOLO_LECTURA,
    },
    Role.CLIENTE: {
        Module.CATEGORIA: SOLO_LECTURA,
        Module.NEGOCIO: SOLO_LECTURA,
        Module.SUCURSAL: SOLO_LECTURA,
        Module.USUARIO: SOLO_LECTURA,
        Module.CANJE: {Action.CREATE, Action.READ},
        Module.OPERACION: {},
        Module.CONFIG_PUNTOS: {},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
        Module.VALE: SOLO_LECTURA,
    },
    Role.SOCIO: {
        Module.CATEGORIA: {},
        Module.NEGOCIO: SOLO_LECTURA,
        Module.SUCURSAL: SOLO_LECTURA,
        Module.USUARIO: SOLO_LECTURA,
        Module.CANJE: {Action.READ, Action.UPDATE},
        Module.OPERACION: {},
        Module.CONFIG_PUNTOS: {},
        Module.MOVIMIENTOS_PUNTOS: {},
        Module.VALE: {},
    },
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, set())
