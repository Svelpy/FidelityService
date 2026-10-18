from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.canje.schemas import CanjeResponse
from app.domains.negocio.schemas import NegocioResponse
from app.domains.operacion.schemas import OperacionResponse
from app.domains.sucursal.schemas import SucursalResponse
from app.domains.users.schemas import UserResponse
from app.domains.vale.schemas import ValeResponse
from app.shared.enums import TipoMovimiento


class MovimientoPuntosResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    tipo_movimiento: TipoMovimiento
    puntos: int
    operacion_id: UUID | None
    canje_id: UUID | None
    movimiento_origen_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "usuario_id": "11111111-1111-4111-8111-111111111111",
                "tipo_movimiento": "ACUMULA",
                "puntos": 150,
                "operacion_id": "33333333-3333-4333-8333-333333333333",
                "canje_id": "44444444-4444-4444-8444-444444444444",
                "movimiento_origen_id": "55555555-5555-4555-8555-555555555555",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
            }
        },
    )


class MovimientoPuntosResponseAudit(MovimientoPuntosResponse):

    created_by: UUID | None

    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "usuario_id": "11111111-1111-4111-8111-111111111111",
                "tipo_movimiento": "ACUMULA",
                "puntos": 150,
                "operacion_id": "33333333-3333-4333-8333-333333333333",
                "canje_id": "44444444-4444-4444-8444-444444444444",
                "movimiento_origen_id": "55555555-5555-4555-8555-555555555555",
                "created_at": "2026-10-12T14:30:00Z",
                "created_by": "44444444-4444-4444-8444-444444444444",
                "updated_at": "2026-10-12T14:30:00Z",
                "updated_by": "44444444-4444-4444-8444-444444444444",
                "is_deleted": True,
                "deleted_at": "2026-10-13T10:15:00Z",
                "deleted_by": "66666666-6666-4666-8666-666666666666",
            }
        },
    )


class MovimientoPuntosDetailResponse(BaseModel):
    data: MovimientoPuntosResponse
    canje: CanjeResponse | None
    operacion: OperacionResponse | None
    sucursal: SucursalResponse | None
    negocio: NegocioResponse | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "data": MovimientoPuntosResponse.model_json_schema()["example"],
                "canje": CanjeResponse.model_json_schema()["example"],
                "operacion": OperacionResponse.model_json_schema()["example"],
                "sucursal": SucursalResponse.model_json_schema()["example"],
                "negocio": NegocioResponse.model_json_schema()["example"],
            }
        },
    )


class MovimientoPuntosListResponse(BaseModel):
    movimiento: MovimientoPuntosResponse
    cliente: UserResponse
    emisor: UserResponse | None
    operacion: OperacionResponse | None
    canje: CanjeResponse | None
    vale: ValeResponse | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "movimiento": MovimientoPuntosResponse.model_json_schema()["example"],
                "cliente": UserResponse.model_json_schema()["example"],
                "emisor": {
                    **UserResponse.model_json_schema()["example"],
                    "id": "77777777-7777-4777-8777-777777777777",
                    "nombre": "Cajero emisor",
                    "role": "CAJERO",
                },
                "operacion": OperacionResponse.model_json_schema()["example"],
                "canje": CanjeResponse.model_json_schema()["example"],
                "vale": ValeResponse.model_json_schema()["example"],
            }
        },
    )


class MovimientoPuntosListMeResponse(BaseModel):
    movimiento: MovimientoPuntosResponse
    operacion: OperacionResponse | None
    canje: CanjeResponse | None
    vale: ValeResponse | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "movimiento": MovimientoPuntosResponse.model_json_schema()["example"],
                "operacion": OperacionResponse.model_json_schema()["example"],
                "canje": CanjeResponse.model_json_schema()["example"],
                "vale": ValeResponse.model_json_schema()["example"],
            }
        },
    )
