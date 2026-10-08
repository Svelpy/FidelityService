# AGENTS.md

Este archivo contiene las reglas que deben aplicarse siempre al trabajar en este backend.

Para detalles de arquitectura, responsabilidades por archivo, ejemplos y decisiones técnicas ampliadas, consultar `ARCHITECTURE.md` solo cuando la tarea lo requiera.

---

## 1. Stack

- Python
- FastAPI
- PostgreSQL
- SQLModel para modelos persistentes
- SQLAlchemy async / `AsyncSession`
- asyncpg
- Pydantic para schemas
- Alembic para migraciones

Regla fundamental:

```text
models.py  → SQLModel
schemas.py → Pydantic
```

Models y schemas son capas independientes.

Nunca hacer herencia entre un modelo persistente y un schema.

La duplicación razonable de campos entre ambas capas es aceptada para mantener desacopladas la persistencia y la API.

---

## 2. Estructura de `app/`

`app/` contiene únicamente estas cinco carpetas principales:

```text
app/
├── core/
├── domains/
├── integrations/
├── middlewares/
└── shared/
```

Además:

```text
app/
├── __init__.py
├── api.py
└── main.py
```

No crear nuevas carpetas raíz dentro de `app/` sin una necesidad arquitectónica explícita.

---

## 3. Responsabilidades principales

### `core/`
Infraestructura fundamental.

Contiene:

```text
base_model.py
config.py
database.py
logging.py
security.py
system_router.py
```

No colocar lógica funcional de dominios dentro de `core/`.

### `domains/`
Funcionalidad de negocio.

Estructura estándar:

```text
<domain>/
├── __init__.py
├── models.py
├── schemas.py
├── services.py
└── routes.py
```

`auth/` incluye además `dependencies.py`.

`error_logs/` es obligatorio y contiene como mínimo su modelo.

### `integrations/`
Adaptadores de proveedores externos.

Ejemplos:

```text
cloudinary.py
resend.py
redis.py
```

Flujo:

```text
service
↓
integration
↓
provider
```

### `middlewares/`
Comportamiento HTTP global.

```text
cors.py
exception_handlers.py
limiter.py
```

### `shared/`
Código realmente reutilizable entre dominios.

No utilizarlo como carpeta miscelánea.

---

## 4. Models

Los modelos persistentes utilizan SQLModel con `table=True`.

Todos los modelos normales heredan del `BaseModel` definido en `core/base_model.py`.

`BaseModel` contiene:

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

`BaseModel` no utiliza `table=True`.

Los models definen exclusivamente:

- columnas;
- primary keys;
- foreign keys;
- relaciones;
- índices;
- `unique`;
- `nullable`;
- restricciones persistentes.

No contienen lógica HTTP ni reglas funcionales de negocio.

### Integridad persistente del dominio

Las siguientes invariantes son obligatorias y deben estar garantizadas por
PostgreSQL mediante constraints, índices, claves foráneas o triggers de
restricción, según corresponda. No es suficiente validarlas solamente en los
services:

- El `slug` de una categoría es único.
- En una operación, `emisor_id` y `receptor_id` deben ser diferentes.
- Todos los factores de conversión deben ser mayores que cero.
- El código de canje es único.
- El código de canje contiene exactamente seis dígitos. Debe persistirse
  como `CHAR(6)` o un tipo textual equivalente, nunca como entero, para
  conservar posibles ceros iniciales. PostgreSQL debe aplicar un `CHECK`
  equivalente a `codigo_canje ~ '^[0-9]{6}$'` además de la restricción
  `UNIQUE`.
- Un vale solo puede canjearse en una sucursal perteneciente al mismo negocio
  que el vale.
- La pertenencia de vales y sucursales al mismo negocio debe garantizarse con
  claves foráneas compuestas. Las tablas referenciadas deben declarar las
  restricciones `UNIQUE` compuestas necesarias para soportarlas.
- Si un usuario tiene el rol `SOCIO`, solo puede asignarse a sucursales cuyo
  negocio sea de tipo `SOCIO`.
- `SOCIO` es un rol de usuario propio y debe formar parte del enum `Role`; no
  debe confundirse con el valor `SOCIO` de `TipoNegocio`.
- Un usuario puede pertenecer como máximo a una sucursal. La relación se
  representa mediante `usuario.sucursal_id`; no se crea una tabla intermedia
  usuario-sucursal.
- La compatibilidad entre el rol del usuario y el tipo de negocio de la
  sucursal debe garantizarse a nivel de base de datos. Cuando no pueda
  expresarse con una clave foránea compuesta o un `CHECK`, debe utilizarse un
  constraint trigger de PostgreSQL mantenido mediante Alembic.
- La cédula de identidad del usuario es obligatoria y única, pues es el
  identificador utilizado para el login. La contraseña se persiste únicamente
  mediante `password_hash`; nunca se almacena la contraseña en texto plano.
- Los importes monetarios se almacenan con `NUMERIC(14, 2)` en PostgreSQL y
  `Decimal` en Python. No se utiliza `float` ni `DOUBLE PRECISION` para dinero.
- En `movimientos_puntos`, las referencias deben cumplir:
  - `ACUMULA`: `operacion_id` obligatorio y `canje_id` nulo.
  - `CANJE`: `canje_id` obligatorio y `operacion_id` nulo.
  - `AJUSTE`: `operacion_id` y `canje_id` nulos.
  - `EXPIRA`: `operacion_id` y `canje_id` nulos.
  Estas combinaciones deben garantizarse con un `CHECK` de PostgreSQL.
- En configuraciones con rango temporal, `end_date` puede ser nulo; cuando
  exista, debe ser posterior a `start_date` mediante un `CHECK`.

Los enums persistentes del dominio son:

```text
tipo_negocio    = MAIN | SOCIO
estado_canje    = PENDIENTE | CANJEADO | EXPIRADO | CANCELADO
tipo_movimiento = ACUMULA | CANJE | AJUSTE | EXPIRA
```

Sus valores deben definirse también como enums Python compartidos en
`app/shared/enums.py`. Los tipos nativos de PostgreSQL y cualquier cambio en
ellos se crean y administran exclusivamente mediante migraciones Alembic; no
mediante SQL ejecutado durante el startup.

Estas tablas son nuevas y deben utilizar nombres de tablas, columnas,
constraints e índices en `snake_case` minúsculo. No se deben introducir
identificadores PostgreSQL entrecomillados en mayúsculas como `"USUARIO"` o
`"Cliente_id"`.

---

## 5. Soft delete y auditoría

La eliminación estándar es lógica.

`delete` debe actualizar:

```text
is_deleted = True
deleted_at
deleted_by
updated_at
updated_by
```

`get` y `list` excluyen por defecto registros con `is_deleted=True`.

La consulta de eliminados debe ser explícita.

Los services son responsables de asignar:

```text
created_by
updated_by
deleted_by
updated_at
deleted_at
```

cuando corresponda.

---

## 6. Schemas

Los schemas utilizan exclusivamente `pydantic.BaseModel`.

Schemas estándar por dominio:

```text
Create
Update
Response
ResponseAudit
```

`ResponseAudit` hereda de `Response`.

Se permiten schemas especiales cuando exista una operación funcional distinta, por ejemplo:

```text
UserUpdateMe
ChangePassword
ResetPassword
```

Los schemas de respuesta que se construyan desde objetos ORM deben utilizar `ConfigDict(from_attributes=True)`.

Las actualizaciones `PATCH` deben usar campos opcionales y los services deben procesarlas con:

```python
model_dump(exclude_unset=True)
```

---

## 7. Validaciones

Separación obligatoria:

```text
Schema
→ formato, estructura y normalización

Service
→ reglas de negocio y validaciones con base de datos

Model / PostgreSQL
→ integridad persistente

Integration
→ restricciones técnicas necesarias para proteger o utilizar al proveedor externo
```

Los validadores reutilizables sin acceso a base de datos viven en:

```text
shared/services/validators.py
```

---

## 8. Services

Los services contienen:

- consultas;
- lógica de negocio;
- creación;
- actualización;
- soft delete;
- transacciones;
- validaciones con base de datos;
- coordinación de integrations.

CRUD estándar:

```text
get
list
create
update
delete
```

No duplicar services si uno existente resuelve correctamente la operación.

Las routes no ejecutan queries directamente.

---

## 9. Routes

Las routes gestionan únicamente:

- HTTP;
- `Depends`;
- path/query parameters;
- schemas;
- status codes;
- llamada al service.

CRUD estándar:

```text
GET    /
GET    /{id}
POST   /
PATCH  /{id}
DELETE /{id}
```

`GET /` devuelve paginación por defecto.

`GET /me` y `PATCH /me` deben reutilizar `get` y `update` cuando la lógica sea equivalente.

---

## 10. Base de datos

`core/database.py` administra:

```text
AsyncEngine
async_sessionmaker
initialize_database
check_database_connection
get_db
close_database
```

Nombres oficiales en `app.state`:

```text
app.state.db_engine
app.state.db_session_factory
```

No utilizar nombres alternativos para estos objetos.

En routes/dependencies, usar normalmente:

```python
Depends(get_db)
```

Código global fuera del flujo normal de `Depends()` puede usar `app.state.db_session_factory`.

---

## 11. Alembic

Las tablas no se crean durante startup.

No crear funciones como:

```text
create_users_table
create_auth_session_table
create_all_tables
```

No usar `SQLModel.metadata.create_all()` como sistema normal de migraciones.

Flujo:

```text
models.py
↓
Alembic autogenerate
↓
revisar migration
↓
alembic upgrade
↓
PostgreSQL
```

Al crear o modificar modelos, garantizar que Alembic pueda descubrirlos.

---

## 12. Config

Toda configuración proviene de `core/config.py`.

No leer `.env` directamente en otros módulos.

`ENVIRONMENT` es la fuente principal de comportamiento:

```text
development
staging
production
test
```

Propiedades como `DEBUG`, expiraciones, cookies y CORS pueden derivarse de `ENVIRONMENT`.

---

## 13. Logging

Todos los módulos utilizan:

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
```

No configurar logging localmente.

`setup_logging(settings)` se ejecuta una sola vez durante el arranque.

---

## 14. Security

`core/security.py` contiene primitivas reutilizables:

```text
password hashing
JWT
refresh tokens
CSRF
one-time tokens
```

No contiene:

```text
login
logout
sesiones
consultas de usuarios
roles
permisos
Depends
cookies
respuestas HTTP
```

`SECRET_KEY` y `CSRF_SECRET_KEY` deben ser diferentes.

---

## 15. Integrations

Las integrations encapsulan SDKs y proveedores externos.

No deben decidir reglas funcionales del dominio.

Pueden contener restricciones técnicas destinadas a proteger al proveedor.

### Cloudinary

Puede validar:

```text
tipo de imagen
bloqueo de SVG
tamaño máximo
```

Guardar la URL segura de la imagen:

```text
image_url
```

Para eliminar o administrar recursos, la integration puede obtener el
`public_id` desde una URL válida de Cloudinary mediante una función dedicada.
La extracción debe permanecer centralizada en `integrations/cloudinary.py`; no
debe duplicarse en routes ni services.

Si el SDK ejecuta operaciones síncronas dentro del backend async, usar un mecanismo como `asyncio.to_thread()`.

### Resend

Resend únicamente envía correo.

La decisión de cuándo y por qué enviar pertenece al service del dominio.

Usar la API async oficial y `idempotency_key` cuando corresponda.

---

## 16. Middlewares

`middlewares/__init__.py` es el punto único de registro:

```python
register_exception_handlers(app, settings)
register_rate_limiter(app)
register_cors(app, settings)
```

### CORS
Solo configura `CORSMiddleware`.

### Limiter
Solo configura SlowAPI y guarda:

```text
app.state.limiter
```

El handler `429` vive únicamente en `exception_handlers.py`.

`memory://` es válido para una sola instancia/proceso efectivo. Si existen varios workers o instancias, usar almacenamiento compartido como Redis.

### Exception handlers

Centraliza:

```text
AppException
RequestValidationError
RateLimitExceeded
StarletteHTTPException
Exception
```

Los errores inesperados:

```text
→ se registran con logging
→ pueden persistirse en ErrorLog
→ no exponen detalles internos fuera de DEBUG
```

El handler global puede utilizar `app.state.db_session_factory` porque no usa el flujo normal de `Depends(get_db)`.

---

## 17. API y main

`api.py` es exclusivamente un agregador de routers.

Estructura:

```text
api_router
├── system_router
└── no_system_router (/api/v1)
```

`main.py` debe mantenerse pequeño.

Puede:

- obtener settings;
- configurar logging;
- crear FastAPI;
- configurar lifespan;
- configurar integrations;
- inicializar PostgreSQL;
- comprobar conexión;
- guardar `db_engine` y `db_session_factory`;
- registrar middlewares;
- incluir `api_router`;
- cerrar recursos.

No debe crear tablas ni contener lógica de negocio.

---

## 18. Dirección de dependencias

Mantener:

```text
routes
↓
services
↓
models
```

Para proveedores:

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

---

## 19. Reglas para cambios

Antes de modificar código:

1. Revisar el código relacionado.
2. Reutilizar funciones existentes.
3. No crear archivos o capas innecesarias.
4. Mantener SQLModel en persistencia y Pydantic en schemas.
5. No hacer herencia entre models y schemas.
6. Mantener queries y reglas de negocio en services.
7. Mantener routes pequeñas.
8. Utilizar el logging global.
9. Utilizar `Settings` como fuente central de configuración.
10. Respetar soft delete y auditoría.
11. Utilizar Alembic para cambios estructurales.
12. Mantener los nombres oficiales de `app.state`.
13. No duplicar handlers ni services.
14. No exponer stack traces ni errores internos fuera de DEBUG.
15. Elegir la solución más simple compatible con esta arquitectura.

---

## 20. Cuándo consultar `ARCHITECTURE.md`

No leer `ARCHITECTURE.md` antes de cada cambio.

Consultarlo cuando la tarea involucre:

- crear un nuevo dominio;
- decidir dónde debe vivir una responsabilidad;
- models, auditoría o soft delete;
- schemas y validaciones;
- acceso a PostgreSQL;
- migraciones Alembic;
- autenticación o seguridad;
- integrations;
- middlewares y exception handlers;
- cambios en `main.py` o `api.py`;
- decisiones arquitectónicas no cubiertas claramente en este archivo.
