from enum import Enum

class Role(str, Enum):
# --- Plataforma: tu equipo, no un negocio cliente ---
    SUPERADMIN = "SUPERADMIN"    # Control total, sin restricciones
    ADMIN = "ADMIN"              # Tu equipo, operativo, no puede eliminar
 
    # --- Negocio: usuarios de las empresas clientes ---
    PROPIETARIO = "PROPIETARIO"  # Dueño de la empresa
    GERENTE = "GERENTE"          # Supervisión: reportes, aprobaciones, gestiona staff
    FINANZAS = "FINANZAS"        # Ve costos/márgenes/reportes financieros; no gestiona staff
    VENDEDOR = "VENDEDOR"        # Vende, crea órdenes, ve stock (sin ver costos)
    ALMACEN = "ALMACEN"          # Gestiona stock/recepción; sin ver precios ni reportes
    USER = "USER" 

class Module(str, Enum):
    # --- Fase 1 ---
    BUSINESS = "business"
    USERS = "users"
    CATEGORY = "category"
    PRODUCTS = "products"              # Sin permisos operativos asignados aún
    META = "meta"

class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
class AuthProvider(str, Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    GITHUB = "GITHUB"
    APPLE = "APPLE"

class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"

class BusinessPlan(str, Enum):
    BASICO = "basico"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class FrontendType(str, Enum):
    TEMPLATE = "template"
    CUSTOM = "custom"

class BillingStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELED = "canceled"

class TitlePosition(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
