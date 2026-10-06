import resend

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def configure_resend(settings: Settings) -> None:
    """Configura el SDK de Resend durante el arranque de la aplicación."""
    if settings.RESEND_API_KEY:
        resend.api_key = settings.RESEND_API_KEY


class ResendService:
    """Adaptador para el envío de correo transaccional mediante Resend."""

    @staticmethod
    async def send_email(
        settings: Settings,
        *,
        to: str | list[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """Envía un correo y devuelve el identificador asignado por Resend."""
        if not settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY no está configurada")

        if not settings.RESEND_FROM_EMAIL:
            raise RuntimeError("RESEND_FROM_EMAIL no está configurado")

        params: resend.Emails.SendParams = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": to,
            "subject": subject,
            "html": html,
            "reply_to": reply_to or settings.RESEND_REPLY_TO,
        }

        if text is not None:
            params["text"] = text

        options = (
            {"idempotency_key": idempotency_key}
            if idempotency_key is not None
            else None
        )
        email = await resend.Emails.send_async(params, options)
        return email["id"]
