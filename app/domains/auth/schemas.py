from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.shared.enums import Role
from app.shared.services.validators import validator_email 


class UserLogin(BaseModel):
    """Schema de entrada para login con email y contraseña"""
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validator_email(value)


class TokenResponse(BaseModel):
    """Schema de respuesta al autenticarse exitosamente"""
    access_token: str
    csrf_token: str
    token_type: str = "bearer"
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt-access-token>",
                "csrf_token": "<csrf-token>",
                "token_type": "bearer",
            }
        }
    )
class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    csrf_token: str

class CurrentUser(BaseModel):
    id: UUID
    role: Role

class TokenClaims(BaseModel):
    sub: UUID
    role: Role
    iat: datetime
    exp: datetime
    jti: str

