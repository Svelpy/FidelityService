from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.enums import AuthProvider, Role, UserStatus
from app.shared.services.validators import (
    validator_names,
    validator_password,
    validator_phone,
    validator_username,
    validator_email,
    validator_birth_date,
)


# ---------------------------------------------------------------------------
# Schemas de escritura (entrada de datos)
# ---------------------------------------------------------------------------

class UserCredentialsData(BaseModel):
    """Credenciales y correo usados al crear un usuario administrativamente."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)



    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validator_password(value)
    
    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validator_email(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "usuario@adamgroup.com.bo",
                "password": "Passw0rd123",
            }
        }
    )


class UserCreate(UserCredentialsData):
    """Schema para crear un usuario desde el panel administrativo."""

    name: str | None = Field(None, min_length=2, max_length=50)
    lastname: str | None = Field(None, min_length=2, max_length=100)
    username: str | None = Field(None, min_length=4, max_length=20)
    phone_number: str | None = Field(None, min_length=6, max_length=16)
    birth_date: datetime | None = None

    role: Role

    @field_validator("name", "lastname", mode="before")
    @classmethod
    def validate_names(cls, value: str | None) -> str | None:
        return validator_names(value)

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        return validator_username(value)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return validator_phone(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: datetime | None) -> datetime | None:
        return validator_birth_date(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "admin.creado@adamgroup.com.bo",
                "password": "Passw0rd123",
                "name": "María",
                "lastname": "García López",
                "username": "maria_garcia",
                "phone_number": "+59170012345",
                "birth_date": "1990-01-01T00:00:00Z",
                "role": "GERENTE",
            }
        },
    )


class UserSelfUpdate(BaseModel):
    """Schema para actualizar datos del propio usuario."""

    name: str | None = Field(None, min_length=2, max_length=50)
    lastname: str | None = Field(None, min_length=2, max_length=100)
    username: str | None = Field(None, min_length=4, max_length=20)
    phone_number: str | None = Field(None, min_length=6, max_length=16)
    birth_date: datetime | None = None

    @field_validator("name", "lastname", mode="before")
    @classmethod
    def validate_names(cls, value: str | None) -> str | None:
        return validator_names(value)

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        return validator_username(value)

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return validator_phone(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls,value: datetime | None) -> datetime | None:
        return validator_birth_date(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "María",
                "lastname": "García López",
                "username": "maria_garcia",
                "phone_number": "+59170099887",
                "birth_date": "1990-01-01T00:00:00Z",
            }
        }
    )
    


AdministrativeUserStatus = Literal[UserStatus.ACTIVE,UserStatus.INACTIVE,UserStatus.SUSPENDED,UserStatus.BANNED]
class UserUpdate(UserSelfUpdate):
    """Schema para actualizar un usuario desde una ruta administrativa."""
    
    role: Role | None = None
    status: AdministrativeUserStatus | None = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "María",
                "lastname": "García López",
                "username": "maria_garcia",
                "phone_number": "+59170099887",
                "birth_date": "1990-01-01T00:00:00Z",
                "status": "ACTIVE",
                "role": "GERENTE",
            }
        }
    )



class AdminResetPassword(BaseModel):
    """Schema para restablecer contraseñas administrativamente."""

    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "new_password": "NuevaPass123",
            }
        }
    )


class PasswordSelfUpdate(AdminResetPassword):
    """Schema para cambiar la contraseña del usuario autenticado."""

    current_password: str = Field(..., min_length=1)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "current_password": "PassActual123",
                "new_password": "NuevaPass123",
            }
        }
    )



# ---------------------------------------------------------------------------
# Schemas de lectura (salida de datos)
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Respuesta de usuario sin contraseña ni datos sensibles."""

    id: PydanticObjectId
    email: EmailStr
    name: str | None = None
    lastname: str | None = None
    username: str | None = None
    role: Role
    phone_number: str | None = None
    birth_date: datetime | None = None
    avatar_url: str | None = None
    
    status: UserStatus
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "usuario@adamgroup.com.bo",
                "name": "María",
                "lastname": "García López",
                "username": "mariagarcia",
                "role": "USER",
                "status": "ACTIVE",
                "avatar_url": None,
                "phone_number": "+59170012345",
                "birth_date": "1990-01-01T00:00:00Z",
                "created_at": "2025-12-19T14:00:00Z",
                "updated_at": "2025-12-19T14:00:00Z",
            }
        },
    )


class UserResponseAudit(UserResponse):
    """Respuesta de usuario completa con datos de auditoría."""
    created_by: PydanticObjectId | None = None
    updated_by: PydanticObjectId | None = None
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: PydanticObjectId | None = None
    auth_provider: AuthProvider
    business_id: PydanticObjectId | None = None
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "business_id": "507f1f77bcf86cd799439000",
                "email": "usuario@adamgroup.com.bo",
                "name": "María",
                "lastname": "García López",
                "username": "mariagarcia",
                "role": "USER",
                "status": "ACTIVE",
                "auth_provider": "LOCAL",
                "avatar_url": None,
                "phone_number": "+59170012345",
                "birth_date": "1990-01-01T00:00:00Z",
                "created_at": "2025-12-19T14:00:00Z",
                "updated_at": "2025-12-19T14:00:00Z",
                "created_by": "507f1f77bcf86cd799439000",
                "updated_by": "507f1f77bcf86cd799439000",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
class UserCreationResponse(BaseModel):
    user: UserResponse | UserResponseAudit
    email: EmailStr
