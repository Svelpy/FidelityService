import asyncio
import html
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_csrf_token,
    create_one_time_token,
    create_refresh_token,
    hash_one_time_token,
    hash_password,
    hash_refresh_token,
    verify_csrf_token,
    verify_password,
)
from app.domains.auth.models import AuthSession, PasswordResetToken
from app.domains.auth.schemas import (
    AuthTokens,
    ForgotPassword,
    ResetPassword,
    UserLogin,
)
from app.domains.users.models import User
from app.integrations.resend import ResendService
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


logger = get_logger(__name__)

PASSWORD_RESET_FRONTEND_PATH = "/reset-password"


class AuthService:

    @staticmethod
    async def _commit(db_session: AsyncSession) -> None:
        try:
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    @staticmethod
    def _get_user_role(user: User) -> Role:
        try:
            return user.role if isinstance(user.role, Role) else Role(user.role)
        except (TypeError, ValueError) as error:
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
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSession:
        now = datetime.now(timezone.utc)
        return AuthSession(
            user_id=user.id,
            family_id=family_id or uuid4(),
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
            created_at=now,
            created_by=user.id,
            updated_at=now,
            updated_by=user.id,
            is_deleted=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    @staticmethod
    def validate_user_access(user: User) -> None:
        """Valida que el usuario no haya sido eliminado."""
        if user.is_deleted:
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
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokens:
        """Autentica un usuario y genera sus tokens."""
        result = await db_session.execute(
            select(User).where(
                User.ci == credentials.ci,
                User.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        password_hash_to_verify = (
            user.password_hash
            if user is not None and user.password_hash
            else DUMMY_PASSWORD_HASH
        )
        password_is_valid = await asyncio.to_thread(
            verify_password,
            credentials.password,
            password_hash_to_verify,
        )
        if user is None or not password_is_valid:
            raise AppException(
                "Cédula o contraseña incorrectas.",
                401,
                ErrorCode.AUTHENTICATION_FAILED,
            )

        AuthService.validate_user_access(user)
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
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db_session.add(auth_session)
        await AuthService._commit(db_session)

        logger.info("Inicio de sesión exitoso: user_id=%s", user.id)

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
        now = datetime.now(timezone.utc)
        await db_session.execute(
            update(AuthSession)
            .where(
                AuthSession.family_id == family_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.is_deleted.is_(False),
            )
            .values(
                revoked_at=now,
                revocation_reason=reason,
                updated_at=now,
                updated_by=AuthSession.user_id,
            )
        )

    @staticmethod
    async def revoke_for_user(
        db_session: AsyncSession,
        user_id: UUID,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        await db_session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.is_deleted.is_(False),
            )
            .values(
                revoked_at=now,
                revocation_reason=reason,
                updated_at=now,
                updated_by=user_id,
            )
        )

    @staticmethod
    async def refresh(
        db_session: AsyncSession,
        refresh_token: str | None,
        csrf_token: str | None,
        settings: Settings,
        user_agent: str | None = None,
        ip_address: str | None = None,
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
                AuthSession.is_deleted.is_(False),
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
                await AuthService._commit(db_session)
                logger.warning(
                    "Reutilización de refresh token detectada: family_id=%s",
                    auth_session.family_id,
                )
            raise AppException(
                "Refresh token ya utilizado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        if auth_session.expires_at <= now:
            auth_session.revoked_at = now
            auth_session.last_used_at = now
            auth_session.revocation_reason = "expired"
            auth_session.updated_at = now
            auth_session.updated_by = auth_session.user_id
            await AuthService._commit(db_session)
            raise AppException(
                "Refresh token expirado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        user_result = await db_session.execute(
            select(User).where(
                User.id == auth_session.user_id,
                User.is_deleted.is_(False),
            )
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            await AuthService.revoke_session_family(
                db_session,
                auth_session.family_id,
                "user_unavailable",
            )
            await AuthService._commit(db_session)
            raise AppException(
                "Refresh token inválido.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        AuthService.validate_user_access(user)
        role = AuthService._get_user_role(user)
        new_refresh_token = create_refresh_token()
        new_csrf_token = create_csrf_token(new_refresh_token, settings)
        new_session = AuthService._build_session(
            user=user,
            refresh_token=new_refresh_token,
            family_id=auth_session.family_id,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db_session.add(new_session)
        await db_session.flush()

        update_result = await db_session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == auth_session.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                AuthSession.is_deleted.is_(False),
            )
            .values(
                revoked_at=now,
                last_used_at=now,
                revocation_reason="rotated",
                replaced_by=new_session.id,
                updated_at=now,
                updated_by=user.id,
            )
        )

        if update_result.rowcount != 1:
            await db_session.rollback()
            raise AppException(
                "Refresh token inválido o ya utilizado.",
                401,
                ErrorCode.REFRESH_FAILED,
            )

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": role.value,
            },
            settings=settings,
        )
        await AuthService._commit(db_session)

        logger.info(
            "Sesión renovada: user_id=%s family_id=%s",
            user.id,
            auth_session.family_id,
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
            select(AuthSession)
            .where(
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
                AuthSession.is_deleted.is_(False),
            )
            .with_for_update()
        )
        auth_session = result.scalar_one_or_none()

        if auth_session is None:
            return

        if auth_session.revoked_at is not None:
            if auth_session.revocation_reason == "rotated":
                await AuthService.revoke_session_family(
                    db_session,
                    auth_session.family_id,
                    "logout",
                )
                await AuthService._commit(db_session)
                logger.info(
                    "Familia de sesión cerrada: user_id=%s family_id=%s",
                    auth_session.user_id,
                    auth_session.family_id,
                )
            return

        await AuthService.revoke_session_family(
            db_session,
            auth_session.family_id,
            "logout",
        )
        await AuthService._commit(db_session)

        logger.info(
            "Sesión cerrada: user_id=%s family_id=%s",
            auth_session.user_id,
            auth_session.family_id,
        )

    @staticmethod
    def _build_password_reset_email(
        nombre: str,
        reset_url: str,
        expire_minutes: int,
    ) -> tuple[str, str]:
        """Construye el contenido HTML y de texto del correo de recuperación."""
        safe_nombre = html.escape(nombre)
        safe_url = html.escape(reset_url, quote=True)
        html_content = (
            f"<p>Hola {safe_nombre},</p>"
            "<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
            f'<p><a href="{safe_url}">Restablecer contraseña</a></p>'
            f"<p>Este enlace vence en {expire_minutes} minutos y solo puede "
            "usarse una vez.</p>"
            "<p>Si no solicitaste este cambio, puedes ignorar este correo.</p>"
        )
        text_content = (
            f"Hola {nombre},\n\n"
            "Recibimos una solicitud para restablecer tu contraseña.\n\n"
            f"Restablece tu contraseña aquí: {reset_url}\n\n"
            f"Este enlace vence en {expire_minutes} minutos y solo puede "
            "usarse una vez.\n\n"
            "Si no solicitaste este cambio, puedes ignorar este correo."
        )
        return html_content, text_content

    @staticmethod
    async def request_password_reset(
        db_session: AsyncSession,
        data: ForgotPassword,
        settings: Settings,
    ) -> None:
        """Genera un token de recuperación y lo envía al email del usuario.

        No revela si la cédula existe o si el usuario tiene email registrado.
        """
        result = await db_session.execute(
            select(User)
            .where(
                User.ci == data.ci,
                User.is_deleted.is_(False),
            )
            .with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None or not user.email:
            await db_session.rollback()
            logger.info("Recuperación de contraseña sin destinatario disponible")
            return

        now = datetime.now(timezone.utc)
        await db_session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
                PasswordResetToken.is_deleted.is_(False),
            )
            .values(
                revoked_at=now,
                updated_at=now,
                updated_by=user.id,
            )
        )

        token = create_one_time_token()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_one_time_token(token),
            expires_at=now
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
            created_at=now,
            created_by=user.id,
            updated_at=now,
            updated_by=user.id,
            is_deleted=False,
        )
        db_session.add(reset_token)
        await AuthService._commit(db_session)

        reset_url = (
            f"{settings.AUTH_FRONTEND_URL.rstrip('/')}"
            f"{PASSWORD_RESET_FRONTEND_PATH}?token={token}"
        )
        html_content, text_content = AuthService._build_password_reset_email(
            user.nombre,
            reset_url,
            settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        )
        try:
            await ResendService.send_email(
                settings,
                to=user.email,
                subject="Restablece tu contraseña",
                html=html_content,
                text=text_content,
                idempotency_key=f"password-reset/{reset_token.id}",
            )
        except Exception:
            logger.exception(
                "No se pudo enviar el correo de recuperación: user_id=%s",
                user.id,
            )
            return

        logger.info("Correo de recuperación enviado: user_id=%s", user.id)

    @staticmethod
    async def reset_password_with_token(
        db_session: AsyncSession,
        data: ResetPassword,
    ) -> None:
        """Restablece la contraseña con un token válido y cierra sus sesiones."""
        invalid_token_error = AppException(
            "El enlace es inválido o expiró.",
            400,
            ErrorCode.PASSWORD_RESET_INVALID,
        )
        now = datetime.now(timezone.utc)

        result = await db_session.execute(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == hash_one_time_token(data.token),
                PasswordResetToken.is_deleted.is_(False),
            )
            .with_for_update()
        )
        reset_token = result.scalar_one_or_none()
        if (
            reset_token is None
            or reset_token.used_at is not None
            or reset_token.revoked_at is not None
            or reset_token.expires_at <= now
        ):
            await db_session.rollback()
            raise invalid_token_error

        user_result = await db_session.execute(
            select(User)
            .where(
                User.id == reset_token.user_id,
                User.is_deleted.is_(False),
            )
            .with_for_update()
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            await db_session.rollback()
            raise invalid_token_error

        reset_token.used_at = now
        reset_token.updated_at = now
        reset_token.updated_by = user.id

        user.password_hash = await asyncio.to_thread(
            hash_password,
            data.new_password,
        )
        user.updated_at = now
        user.updated_by = user.id

        await AuthService.revoke_for_user(
            db_session,
            user.id,
            "password_reset",
        )
        await AuthService._commit(db_session)

        logger.info("Contraseña restablecida por token: user_id=%s", user.id)
