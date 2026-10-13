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
        Module.OPERACION: {Action.CREATE, Action.READ},
        Module.CANJE: {Action.READ, Action.UPDATE},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.CLIENTE: {
        Module.OPERACION: SOLO_LECTURA,
        Module.CANJE: {Action.CREATE, Action.READ},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
    Role.SOCIO: {
        Module.OPERACION: {Action.CREATE, Action.READ},
        Module.CANJE: {Action.READ, Action.UPDATE},
        Module.MOVIMIENTOS_PUNTOS: SOLO_LECTURA,
    },
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, set())
