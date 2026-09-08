from uuid import uuid4

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from app.core.config import Settings
import hashlib
import hmac
import secrets

# Hashing de contraseñas con Argon2
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("dummy-password")



def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False

def create_access_token(
    data: Dict[str, Any], 
    settings: Settings,
    expires_delta: timedelta | None = None,
    ) -> str:
    """
    Crear token JWT de acceso
    Args:
        data: Datos a incluir en el token (sub, role, business_id)
        expires_delta: Tiempo de expiración personalizado
    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    #Añadimos  iat - exp - jti
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update(
        {
            "iat": now,
            "exp": expire,
            "jti": str(uuid4()),
        })
    #----------------------------------
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(
    token: str, 
    settings: Settings,
    ) -> Optional[Dict[str, Any]]:
    """
    Decodificar y verificar token JWT
    Args:
        token: Token JWT a decodificar
        
    Returns:
        Payload del token si es válido, None si no es válido
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None



def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_csrf_token(refresh_token: str,settings: Settings) -> str:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"),refresh_token.encode("utf-8"),hashlib.sha256).hexdigest()

def verify_csrf_token(refresh_token: str,csrf_token: str,settings: Settings) -> bool:
    expected_token = create_csrf_token(refresh_token, settings)
    return hmac.compare_digest(expected_token,csrf_token)

def create_one_time_token() -> str:
    return secrets.token_urlsafe(32)


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()