from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.canje.schemas import CanjeResponse
from app.domains.negocio.schemas import NegocioResponse
from app.domains.operacion.schemas import OperacionResponse
from app.domains.sucursal.schemas import SucursalResponse
from app.shared.enums import TipoMovimiento


class MovimientoPuntosResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    tipo_movimiento: TipoMovimiento
    puntos: int
    operacion_id: UUID | None
    canje_id: UUID | None
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
                "canje_id": None,
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
                "canje_id": None,
                "created_at": "2026-10-12T14:30:00Z",
                "created_by": "44444444-4444-4444-8444-444444444444",
                "updated_at": "2026-10-12T14:30:00Z",
                "updated_by": "44444444-4444-4444-8444-444444444444",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )


class MovimientoPuntosDetailResponse(BaseModel):
    data: MovimientoPuntosResponse
    canje: CanjeResponse | None
    operacion: OperacionResponse | None
    sucursal: SucursalResponse | None
    negocio: NegocioResponse | None
