"""
shared/services/permissions.py

Única fuente de verdad de "quién puede hacer qué, sobre qué módulo".
Si agregás un rol o un módulo nuevo, TODO el cambio pasa por este
archivo — no se tocan las rutas.
"""

from app.shared.enums import Role, Module, Action

# Roles que son "tu equipo" (no pertenecen a un negocio cliente puntual).
# Se usan para: (1) saltear el chequeo de tenant/business_id,
#               (2) decidir qué rutas "sin business_id" están permitidas
#                   (crear empresa, listar empresas, etc).
PLATFORM_ROLES = {Role.SUPERADMIN, Role.ADMIN}
STORE_ROLES = {Role.PROPIETARIO,Role.GERENTE,Role.FINANZAS,Role.VENDEDOR,Role.ALMACEN,Role.USER,}

ALL_ACTIONS = {Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}
SIN_ELIMINAR = {Action.CREATE, Action.READ, Action.UPDATE}
SIN_ELIMINAR_SIN_CREAR = {Action.READ, Action.UPDATE}
SOLO_LECTURA = {Action.READ}

# dict[Role, dict[Module, set[Action]]]
# Un módulo ausente en el dict de un rol == sin acceso a ese módulo
# (ni siquiera lectura).
ROLE_PERMISSIONS: dict[Role, dict[Module, set[Action]]] = {
    Role.SUPERADMIN: {
        Module.USERS: ALL_ACTIONS,
        Module.CATEGORY: ALL_ACTIONS,
        Module.PRODUCTS: ALL_ACTIONS,
        Module.BUSINESS: ALL_ACTIONS,
        Module.META: SIN_ELIMINAR_SIN_CREAR,
    },
    Role.ADMIN: {
        Module.USERS: SIN_ELIMINAR,
        Module.CATEGORY: SIN_ELIMINAR,
        Module.PRODUCTS: SIN_ELIMINAR,
        Module.BUSINESS: SIN_ELIMINAR,
        Module.META: SIN_ELIMINAR_SIN_CREAR,
    },
    Role.PROPIETARIO: {
        Module.USERS: ALL_ACTIONS,
        Module.CATEGORY: ALL_ACTIONS,
        Module.PRODUCTS: ALL_ACTIONS,
        Module.BUSINESS: SIN_ELIMINAR_SIN_CREAR,
        Module.META: SIN_ELIMINAR_SIN_CREAR,
    },
    Role.GERENTE: {
        Module.USERS: SIN_ELIMINAR,
        Module.CATEGORY: ALL_ACTIONS,
        Module.PRODUCTS: ALL_ACTIONS,
        Module.BUSINESS: SIN_ELIMINAR_SIN_CREAR,
        Module.META: SIN_ELIMINAR_SIN_CREAR,
    },

    #Role.FINANZAS: {},
    #Role.VENDEDOR: {},
    #Role.ALMACEN: {},
    Role.USER: {},
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, set())
