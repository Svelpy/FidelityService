# ARCHITECTURE.md

Documento de referencia de arquitectura del backend.

Este archivo amplía las reglas resumidas en `AGENTS.md`. No es necesario leerlo para cada cambio pequeño. Debe consultarse cuando se trabaje sobre arquitectura, persistencia, nuevos dominios, seguridad, integrations, middlewares o decisiones estructurales.

---

# 1. Objetivo

La aplicación busca una arquitectura simple, explícita y modular.

La estructura evita capas adicionales como repositories, controllers, managers o use cases mientras no exista una necesidad real.

Arquitectura funcional principal:

```text
routes
↓
services
↓
models
```

Componentes auxiliares:

```text
schemas
dependencies
integrations
shared
core
```

---

# 2. Stack

- Python
- FastAPI
- PostgreSQL
- SQLModel
- SQLAlchemy async
- asyncpg
- Pydantic
- Alembic

Persistencia y API permanecen desacopladas:

```text
models.py  → SQLModel
schemas.py → Pydantic
```

Nunca existe herencia entre ambas capas.

---

# 3. Estructura de la aplicación

```text
app/
├── __init__.py
├── api.py
├── main.py
│
├── core/
│   ├── __init__.py
│   ├── base_model.py
│   ├── config.py
│   ├── database.py
│   ├── logging.py
│   ├── security.py
│   └── system_router.py
│
├── domains/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   └── routes.py
│   ├── error_logs/
│   │   ├── __init__.py
│   │   └── models.py
│   └── <domain>/
│       ├── __init__.py
│       ├── models.py
│       ├── schemas.py
│       ├── services.py
│       └── routes.py
│
├── integrations/
│   ├── __init__.py
│   ├── cloudinary.py
│   ├── resend.py
│   └── <integration>.py
│
├── middlewares/
│   ├── __init__.py
│   ├── cors.py
│   ├── exception_handlers.py
│   └── limiter.py
│
└── shared/
    ├── __init__.py
    ├── enums.py
    ├── services/
    │   ├── __init__.py
    │   ├── permissions.py
    │   ├── slug.py
    │   └── validators.py
    ├── schemas/
    │   ├── __init__.py
    │   ├── errors.py
    │   ├── pagination.py
    │   └── tree.py
    └── errors/
        ├── __init__.py
        ├── codes.py
        └── exceptions.py
```

---

# 4. Core

`core/` contiene infraestructura fundamental de la aplicación.

No contiene lógica funcional de dominios.

## 4.1 Base model

`core/base_model.py` contiene el modelo base de persistencia.

Se implementa con SQLModel y no representa una tabla propia.

Campos comunes:

```text
id
created_at
created_by
updated_at
updated_by
is_deleted
deleted_at
deleted_by
```

Los modelos concretos heredan de él y declaran `table=True`.

Ejemplo conceptual:

```python
class User(BaseModel, table=True):
    __tablename__ = "users"
```

### Auditoría

Creación:

```text
created_at → automático
updated_at → automático
created_by → service
updated_by → service
```

Actualización:

```text
created_at → no cambia
created_by → no cambia
updated_at → service
updated_by → service
```

Eliminación lógica:

```text
is_deleted = True
deleted_at = now
deleted_by = current_user_id
updated_at = now
updated_by = current_user_id
```

## 4.2 Soft delete

`delete` realiza eliminación lógica por defecto.

`get` y `list` excluyen `is_deleted=True`.

La consulta de registros eliminados debe ser explícita.

## 4.3 Config

`core/config.py` utiliza `pydantic-settings`.

`Settings` es la única fuente de configuración.

`get_settings()` usa `lru_cache`.

No leer `.env` desde otros módulos.

Entornos:

```text
development
staging
production
test
```

`DEBUG` se deriva de `ENVIRONMENT`.

También pueden derivarse:

```text
CORS_ORIGINS_LIST
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
REFRESH_TOKEN_COOKIE_SECURE
```

Esto evita configuraciones contradictorias como `ENVIRONMENT=production` y `DEBUG=true`.

## 4.4 Database

`core/database.py` administra exclusivamente PostgreSQL.

Responsabilidades:

```text
resolver DATABASE_URL
crear AsyncEngine
crear async_sessionmaker
inicializar infraestructura
comprobar conexión
proporcionar sesión por request
cerrar engine
```

Funciones conceptuales:

```text
_get_database_url
create_database_engine
create_session_factory
initialize_database
check_database_connection
get_db
close_database
```

Configuración:

```text
create_async_engine
pool_pre_ping=True
echo=settings.DEBUG

async_sessionmaker
expire_on_commit=False
autoflush=False
```

### App state

Nombres oficiales:

```text
app.state.db_engine
app.state.db_session_factory
```

`system_router.py` consulta `db_engine`.

`get_db()` y el global exception handler pueden consultar `db_session_factory`.

No usar nombres alternativos como:

```text
app.state.database
```

### `get_db()`

Está diseñado como dependency de FastAPI:

```python
session: AsyncSession = Depends(get_db)
```

Utiliza `yield` y la session factory almacenada en `app.state`.

Código fuera del flujo normal de dependencies puede abrir sesiones directamente desde `db_session_factory`.

## 4.5 Logging

`core/logging.py` expone:

```text
setup_logging
get_logger
```

Configuración estándar:

```python
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

Uso:

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
```

No configurar logging localmente en otros módulos.

## 4.6 Security

`core/security.py` contiene primitivas reutilizables.

Contraseñas:

```text
PasswordHash.recommended()
hash_password
verify_password
DUMMY_PASSWORD_HASH
```

JWT:

```text
create_access_token
decode_access_token
```

Claims mínimos:

```text
iat
exp
jti
```

Refresh tokens:

```text
create_refresh_token
hash_refresh_token
```

CSRF:

```text
create_csrf_token
verify_csrf_token
```

One-time tokens:

```text
create_one_time_token
hash_one_time_token
```

Claves separadas:

```text
SECRET_KEY
CSRF_SECRET_KEY
```

`security.py` no contiene login, logout, sesiones, permisos, cookies, Depends ni respuestas HTTP.

## 4.7 System router

`core/system_router.py` contiene endpoints técnicos.

### `GET /`

En development puede redirigir a `/docs`.

En otros entornos devuelve estado mínimo de la aplicación.

### `GET /health`

Funciona como readiness probe.

Consulta `app.state.db_engine` y delega la comprobación a:

```text
check_database_connection()
```

Respuestas técnicas como `/health` no están obligadas a usar el `ErrorResponse` funcional.

HTTP:

```text
200 → healthy
503 → unavailable
```

Nunca exponer excepciones internas, stack traces, credenciales o connection strings.

---

# 5. Alembic y PostgreSQL

PostgreSQL utiliza tablas.

SQLModel describe la estructura; Alembic la materializa.

```text
models.py
↓
SQLModel.metadata
↓
Alembic
↓
PostgreSQL
```

No crear tablas durante startup.

No crear funciones específicas como:

```text
create_users_table
create_auth_session_table
create_all_tables
```

No utilizar `SQLModel.metadata.create_all()` como estrategia normal de migración.

Flujo:

```bash
alembic revision --autogenerate -m "descripcion"
alembic upgrade head
```

Alembic debe importar o descubrir los modelos antes de establecer:

```python
target_metadata = SQLModel.metadata
```

Las migrations autogeneradas siempre deben revisarse.

---

# 6. Domains

Cada funcionalidad importante vive en un dominio propio.

Estructura:

```text
<domain>/
├── __init__.py
├── models.py
├── schemas.py
├── services.py
└── routes.py
```

No dividir más el dominio salvo necesidad real.

---

# 7. Models

Los models utilizan SQLModel y `table=True`.

Representan:

```text
columnas
primary keys
foreign keys
relationships
índices
unique
nullable
constraints
```

No contienen:

```text
lógica HTTP
reglas funcionales
queries de endpoints
```

---

# 8. Schemas

Los schemas utilizan Pydantic puro.

No utilizan SQLModel como clase base.

Schemas estándar:

```text
Create
Update
Response
ResponseAudit
```

## Create

Incluye únicamente campos que el cliente puede proporcionar.

No incluye normalmente auditoría ni ID.

## Update

Los campos modificables son opcionales para `PATCH`.

Los services utilizan:

```python
data.model_dump(exclude_unset=True)
```

## Response

Debe poder construirse desde objetos ORM mediante:

```python
ConfigDict(from_attributes=True)
```

## ResponseAudit

Hereda de `Response` y añade los campos de auditoría que deban exponerse.

## Schemas especiales

Se permiten cuando representan una operación distinta:

```text
UserUpdateMe
ChangePassword
ResetPassword
TreeResponse
ImageResponse
```

---

# 9. Validaciones

Distribución:

```text
Pydantic Schema
→ formato, estructura, normalización

Service
→ reglas de negocio y consultas necesarias para validar

SQLModel/PostgreSQL
→ integridad persistente

Integration
→ restricciones técnicas del proveedor
```

Ejemplo de email:

```text
Schema:
- EmailStr
- longitud

Service:
- comprobar que no exista

Model:
- nullable=False
- unique=True
- max_length
```

Los validadores reutilizables sin base de datos viven en:

```text
shared/services/validators.py
```

---

# 10. Services

Los services contienen la lógica funcional.

CRUD estándar:

```text
get
list
create
update
delete
```

También pueden existir:

```text
get_tree
upload_image
delete_image
change_password
activate
restore
```

Los services:

- ejecutan queries;
- aplican reglas de negocio;
- coordinan transacciones;
- actualizan auditoría;
- llaman integrations;
- lanzan `AppException` cuando corresponde.

No construyen respuestas HTTP.

---

# 11. Routes

Las routes gestionan HTTP.

CRUD estándar:

```text
GET    /
GET    /{id}
POST   /
PATCH  /{id}
DELETE /{id}
```

Gestionan:

```text
Depends
path parameters
query parameters
request schemas
response schemas
status codes
```

No ejecutan queries ni llaman directamente SDKs externos.

## `/me`

Si existen:

```text
GET /me
PATCH /me
```

deben reutilizar `get` y `update` cuando la lógica sea equivalente.

La diferencia puede estar únicamente en cómo se obtiene el ID y en el schema permitido.

---

# 12. Auth

`domains/auth/` contiene:

```text
__init__.py
dependencies.py
models.py
schemas.py
services.py
routes.py
```

`dependencies.py` contiene funciones usadas mediante `Depends()`.

Ejemplos:

```text
get_current_user
get_current_user_id
require_authenticated_user
require_permission
```

`core/security.py` proporciona primitivas.

`auth/services.py` implementa el flujo funcional de autenticación.

---

# 13. Error logs

`domains/error_logs/` es obligatorio.

Como mínimo:

```text
__init__.py
models.py
```

`ErrorLog` persiste errores inesperados capturados por el handler global.

Campos útiles:

```text
status
message
stack
path
method
ip_address
user_agent
user_id
```

Puede añadirse `services.py` si se quiere encapsular posteriormente la persistencia.

No necesita routes o schemas mientras no exista una API para consultar esos registros.

---

# 14. Integrations

`integrations/` encapsula proveedores externos.

No debe contener decisiones funcionales del dominio.

Puede configurar SDKs durante startup.

Todas las integrations usan el logger global.

## 14.1 Cloudinary

Responsabilidades:

```text
configure_cloudinary
upload_image
delete_image
safe_delete_image
```

Puede validar técnicamente:

```text
que sea imagen
bloquear SVG
máximo 5 MB
```

Estas reglas protegen el proveedor y pueden permanecer en la integration.

Si el SDK es síncrono dentro de código async, usar:

```python
await asyncio.to_thread(...)
```

Guardar:

```text
image_url
image_public_id
```

en columnas separadas.

No extraer `public_id` desde la URL cuando Cloudinary ya lo devuelve.

## 14.2 Resend

Responsabilidades:

```text
configure_resend
send_email
```

Puede recibir:

```text
to
subject
html
text
reply_to
idempotency_key
```

Utiliza:

```python
await resend.Emails.send_async(...)
```

Debe devolver el identificador asignado por Resend.

La integration no decide cuándo ni por qué se envía un correo.

---

# 15. Middlewares

Estructura:

```text
middlewares/
├── __init__.py
├── cors.py
├── exception_handlers.py
└── limiter.py
```

## 15.1 CORS

`cors.py` registra únicamente `CORSMiddleware`.

Usa:

```text
settings.CORS_ORIGINS_LIST
allow_credentials=True
```

Métodos:

```text
GET
POST
PATCH
DELETE
```

Headers:

```text
Authorization
Content-Type
Accept
Origin
X-Requested-With
X-CSRF-Token
```

## 15.2 Limiter

`limiter.py` configura SlowAPI.

Configuración actual:

```text
default_limits = 300/minute
storage_uri = memory://
strategy = fixed-window
headers_enabled = False
```

Registra:

```text
app.state.limiter
SlowAPIASGIMiddleware
```

No contiene el handler `429`.

Si existen varios workers o instancias, sustituir `memory://` por storage compartido como Redis.

## 15.3 Exception handlers

`exception_handlers.py` registra:

```text
AppException
RequestValidationError
RateLimitExceeded
StarletteHTTPException
Exception
```

### AppException

Formato:

```json
{
  "status": "fail",
  "code": "...",
  "message": "...",
  "details": {}
}
```

401 añade:

```text
WWW-Authenticate: Bearer
```

### Validation

422:

```json
{
  "status": "fail",
  "code": "VALIDATION_ERROR",
  "message": "Los datos enviados no son válidos.",
  "details": {}
}
```

### Rate limit

429:

```json
{
  "status": "fail",
  "code": "HTTP_429",
  "message": "Demasiadas solicitudes. Intenta nuevamente más tarde.",
  "details": {}
}
```

Puede devolver:

```text
Retry-After
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```

### HTTP exceptions

Código:

```text
HTTP_<status>
```

Conserva `exc.headers`.

### Global Exception

En DEBUG:

```text
logger
mensaje real
stack trace en respuesta
```

Fuera de DEBUG:

```text
logger
persistencia en ErrorLog
respuesta genérica 500
```

La persistencia usa:

```text
request.app.state.db_session_factory
```

porque el exception handler global no usa el flujo normal de `Depends(get_db)`.

Si guardar el error falla, debe registrarse con `logger.exception()` sin provocar un segundo fallo.

## 15.4 Registro global

`middlewares/__init__.py` expone:

```python
register_all_middlewares(app, settings)
```

Orden actual:

```python
register_exception_handlers(app, settings)
register_rate_limiter(app)
register_cors(app, settings)
```

---

# 16. Shared

`shared/` contiene código reutilizable entre dominios.

No es una carpeta para código sin ubicación clara.

## 16.1 Enums

Todos los enums reutilizables están en:

```text
shared/enums.py
```

Un enum estrictamente local puede declararse donde se usa.

## 16.2 Permissions

`shared/services/permissions.py` contiene:

```text
roles
modules
actions
estructura de permisos
```

Expone:

```python
has_permission(role, module, action) -> bool
```

## 16.3 Slug

`shared/services/slug.py` contiene generadores reutilizables.

## 16.4 Validators

`shared/services/validators.py` contiene validadores reutilizables sin acceso a base de datos.

## 16.5 Shared schemas

```text
shared/schemas/errors.py
shared/schemas/pagination.py
shared/schemas/tree.py
```

## 16.6 Shared errors

```text
shared/errors/codes.py
shared/errors/exceptions.py
```

`codes.py` contiene identificadores estables.

`exceptions.py` contiene `AppException`.

Flujo:

```text
Service
↓
AppException
↓
Exception Handler
↓
ErrorResponse
```

---

# 17. API Router

`app/api.py` agrega routers.

```text
api_router
├── system_router
└── no_system_router
```

`no_system_router` usa:

```text
/api/v1
```

Los routers funcionales se incluyen allí.

`api.py` no contiene lógica de negocio.

---

# 18. Main

`app/main.py` es el punto de composición.

Puede:

```text
get_settings
setup_logging
crear FastAPI
configurar lifespan
configure_cloudinary
configure_resend
initialize_database
check_database_connection
guardar db_engine
guardar db_session_factory
register_all_middlewares
include api_router
close_database
```

No crea tablas.

No contiene CRUD ni lógica de negocio.

## Lifespan

Flujo:

```text
configure integrations
↓
initialize_database
↓
check_database_connection
↓
app.state.db_engine
app.state.db_session_factory
↓
yield
↓
close_database
```

## Uvicorn

Si se conserva ejecución directa:

```python
if __name__ == "__main__":
```

usar:

```python
reload=settings.DEBUG
```

---

# 19. Flujo general

Request normal:

```text
HTTP
↓
Route
↓
Dependencies
↓
Pydantic Schema
↓
Service
↓
SQLModel
↓
PostgreSQL
```

Con proveedor:

```text
Route
↓
Service
↓
Integration
↓
Provider
```

Error funcional:

```text
Service
↓
AppException
↓
Exception Handler
↓
ErrorResponse
```

Error inesperado:

```text
Exception
↓
Global Exception Handler
├── logger
├── ErrorLog
└── 500 seguro
```

---

# 20. Dirección de dependencias

Preferir:

```text
routes
↓
services
↓
models
```

y:

```text
services
↓
integrations
```

Evitar:

```text
models → services
models → routes
services → routes
schemas → routes
integrations → routes
```

La dependencia directa de `middlewares/exception_handlers.py` hacia `ErrorLog` es una excepción limitada al registro global de errores.

---

# 21. Creación de un nuevo dominio

Orden recomendado:

```text
1. models.py
2. schemas.py
3. services.py
4. routes.py
5. registrar router en api.py
6. registrar/descubrir modelo para Alembic
7. generar migration
8. revisar migration
9. aplicar migration
```

Antes de programar identificar:

```text
campos persistentes
relaciones
Create
Update
Response
ResponseAudit
validaciones
reglas de negocio
permisos
endpoints
integrations necesarias
```

---

# 22. Prohibiciones principales

No hacer:

```text
schema heredando de model
model heredando de schema
SQLModel usado como schema API
queries en routes
lógica funcional en schemas
lógica HTTP en models
SDK externo directamente desde routes
lecturas dispersas del .env
logging configurado localmente
create_all() como sistema de migrations
creación manual de tablas durante startup
delete físico por defecto
get/list mostrando eliminados por defecto
duplicación de handlers
shared como carpeta miscelánea
```

---

# 23. Principio de ubicación

```text
Infraestructura
→ core

Negocio
→ domains

Proveedor externo
→ integrations

HTTP global
→ middlewares

Código transversal
→ shared
```

Dentro de un dominio:

```text
Persistencia
→ models.py

Entrada/salida
→ schemas.py

Operaciones y negocio
→ services.py

HTTP
→ routes.py

Dependencias de auth
→ auth/dependencies.py
```

---

# 24. Principio de simplicidad

No introducir automáticamente:

```text
repositories
controllers
managers
use_cases
```

No dividir archivos por crecimiento hipotético.

Crear una abstracción únicamente cuando exista una necesidad real.

Preferir siempre código explícito, predecible y consistente.
