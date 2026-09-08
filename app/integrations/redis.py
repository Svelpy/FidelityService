from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL no esta configurada")

    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        health_check_interval=30,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def get_redis_client(request: Request) -> Redis:
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        raise RuntimeError("Cliente Redis no inicializado")
    return redis_client
