from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    hash_refresh_token,
    verify_csrf_token,
    verify_password,
)
from app.domains.auth.models import AuthSession
from app.domains.auth.schemas import AuthTokens, UserLogin
from app.domains.users.models import User
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class AuthService:

    @staticmethod
    def _get_user_role(user: User) -> Role:
        try:
            return user.role if isinstance(user.role, Role) else Role(user.role)
        except ValueError as error:
            raise AppException(
                "El rol del usuario no es válido.",
                401,
                ErrorCode.AUTHENTICATION_FAILED,
            ) from error

    @staticmethod
    def _build_session(
        user: User,
        refresh_token: str,
        expires_at: datetime,
        family_id: UUID | None = None,
    ) -> AuthSession:
        now = datetime.now(timezone.utc)
        audit_now = now.replace(tzinfo=None)
        return AuthSession(
            user_id=user.id,
            family_id=family_id or uuid4(),
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
            create_at=audit_now,
            create_by=user.id,
            update_at=audit_now,
            update_by=user.id,
            is_delete=False,
        )

    @staticmethod
    async def validate_user_access(user: User) -> None:
        """Valida que el usuario no haya sido eliminado."""
        if user.is_delete:
            raise AppException(
                "Usuario no disponible.",
                401,
                ErrorCode.AUTHENTICATION_FAILED,
            )

    @staticmethod
    async def login(
        db_session: AsyncSession,
        credentials: UserLogin,
        settings: Settings,
    ) -> AuthTokens:
        """Autentica un usuario y genera sus tokens."""
        result = await db_session.execute(
            select(User).where(
                User.email == str(credentials.email),
                User.is_delete.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        password_hash_to_verify = (
            user.password_hash
            if user is not None and user.password_hash
            else DUMMY_PASSWORD_HASH
        )
        password_is_valid = verify_password(
            credentials.password,
            password_hash_to_verify,
        )
        if user is None or not password_is_valid:
            raise AppException(
                "Email o contraseña incorrectos.",
                401,
                ErrorCode.AUTHENTICATION_FAILED,
            )

        await AuthService.validate_user_access(user)
        role = AuthService._get_user_role(user)

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": role.value,
            },
            settings=settings,
        )

        refresh_token = create_refresh_token()
        csrf_token = create_csrf_token(refresh_token, settings)
        auth_session = AuthService._build_session(
            user=user,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db_session.add(auth_session)

        try:
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )

    @staticmethod
    async def revoke_session_family(
        db_session: AsyncSession,
        family_id: UUID,
        reason: str,
    ) -> None:
        await db_session.execute(
            update(AuthSession)
            .where(
                AuthSession.family_id == family_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(timezone.utc),
                revocation_reason=reason,
            )
        )

    @staticmethod
    async def refresh(
        db_session: AsyncSession,
        refresh_token: str | None,
        csrf_token: str | None,
        settings: Settings,
    ) -> AuthTokens:
        if not refresh_token:
            raise AppException(
                "Refresh token requerido.",
                401,
                ErrorCode.REFRESH_FAILED,
            )
        if not csrf_token or not verify_csrf_token(
            refresh_token,
            csrf_token,
            settings,
        ):
            raise AppException(
                "CSRF token inválido.",
                403,
                ErrorCode.CSRF_INVALID,
            )

        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            select(AuthSession)
            .where(
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
            )
            .with_for_update()
        )
        auth_session = result.scalar_one_or_none()

        if auth_session is None:
            raise AppException(
                "Refresh token inválido.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        if auth_session.revoked_at is not None:
            if (
                auth_session.revocation_reason == "rotated"
                and auth_session.replaced_by is not None
            ):
                await AuthService.revoke_session_family(
                    db_session,
                    auth_session.family_id,
                    "reuse_detected",
                )
                await db_session.commit()
            raise AppException(
                "Refresh token ya utilizado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        if auth_session.expires_at <= now:
            raise AppException(
                "Refresh token expirado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        user_result = await db_session.execute(
            select(User).where(
                User.id == auth_session.user_id,
                User.is_delete.is_(False),
            )
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise AppException(
                "Usuario no encontrado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        await AuthService.validate_user_access(user)
        role = AuthService._get_user_role(user)
        new_refresh_token = create_refresh_token()
        new_csrf_token = create_csrf_token(new_refresh_token, settings)
        new_session = AuthService._build_session(
            user=user,
            refresh_token=new_refresh_token,
            family_id=auth_session.family_id,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db_session.add(new_session)
        await db_session.flush()

        update_result = await db_session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == auth_session.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .values(
                revoked_at=now,
                last_used_at=now,
                revocation_reason="rotated",
                replaced_by=new_session.id,
            )
        )

        if update_result.rowcount != 1:
            await db_session.rollback()
            raise AppException(
                "Refresh token inválido o ya utilizado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        try:
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": role.value,
            },
            settings=settings,
        )

        return AuthTokens(
            access_token=access_token,
            refresh_token=new_refresh_token,
            csrf_token=new_csrf_token,
        )

    @staticmethod
    async def logout(
        db_session: AsyncSession,
        refresh_token: str | None,
        csrf_token: str | None,
        settings: Settings,
    ) -> None:
        if not refresh_token:
            return
        if not csrf_token or not verify_csrf_token(
            refresh_token,
            csrf_token,
            settings,
        ):
            raise AppException(
                "CSRF token inválido.",
                403,
                ErrorCode.CSRF_INVALID,
            )

        result = await db_session.execute(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
            )
        )
        auth_session = result.scalar_one_or_none()

        if auth_session is None or auth_session.revoked_at is not None:
            return

        now = datetime.now(timezone.utc)
        auth_session.revoked_at = now
        auth_session.last_used_at = now
        auth_session.revocation_reason = "logout"

        try:
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise
