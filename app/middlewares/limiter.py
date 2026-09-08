import hashlib
import logging

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.integrations.redis import get_redis_client


logger = logging.getLogger(__name__)

_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class RateLimitService:
    """Rate limiter distribuido basado en una ventana fija de Redis."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis_client = redis_client

    @staticmethod
    def _build_key(scope: str, identity: str) -> str:
        identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"yari:ratelimit:{scope}:{identity_hash}"

    async def check(
        self,
        *,
        scope: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        key = self._build_key(scope, identity)

        try:
            result = await self._redis_client.eval(
                _FIXED_WINDOW_SCRIPT,
                1,
                key,
                window_seconds,
            )
        except RedisError:
            logger.exception("Redis no esta disponible para rate limiting")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio no esta disponible temporalmente.",
            ) from None

        current_count = int(result[0])
        retry_after = max(int(result[1]), 1)
        if current_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta nuevamente mas tarde.",
                headers={"Retry-After": str(retry_after)},
            )


def get_rate_limit_service(
    redis_client: Redis = Depends(get_redis_client),
) -> RateLimitService:
    return RateLimitService(redis_client)


def _get_client_ip(request: Request) -> str:
    if request.client is None or request.client.host is None:
        return "unknown"
    return request.client.host


async def rate_limit_ip(
    request: Request,
    service: RateLimitService = Depends(get_rate_limit_service),
    settings: Settings = Depends(get_settings),
) -> None:
    await service.check(
        scope="ip:api",
        identity=_get_client_ip(request),
        limit=settings.RATE_LIMIT_IP_PER_MINUTE,
        window_seconds=60,
    )


def rate_limit_ip_endpoint(
    scope: str,
    setting_name: str,
    window_seconds: int,
):
    async def dependency(
        request: Request,
        service: RateLimitService = Depends(get_rate_limit_service),
        settings: Settings = Depends(get_settings),
    ) -> None:
        await service.check(
            scope=scope,
            identity=_get_client_ip(request),
            limit=getattr(settings, setting_name),
            window_seconds=window_seconds,
        )

    return dependency
