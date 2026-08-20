import redis
from app.config import get_settings

settings = get_settings()

# Redis客户端 - 延迟初始化，避免Redis不可用时启动失败
_redis_client = None

def get_redis_client():
    """获取Redis客户端，延迟初始化"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # 测试连接
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


def cache_get(key: str) -> str | None:
    """从Redis获取缓存"""
    try:
        client = get_redis_client()
        if client is None:
            return None
        return client.get(key)
    except Exception:
        return None


def cache_set(key: str, value: str, ttl: int = None) -> bool:
    """设置Redis缓存"""
    try:
        client = get_redis_client()
        if client is None:
            return False
        if ttl is None:
            ttl = settings.REDIS_CACHE_TTL
        return client.setex(key, ttl, value)
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    """删除Redis缓存"""
    try:
        client = get_redis_client()
        if client is None:
            return False
        return client.delete(key) > 0
    except Exception:
        return False


def cache_clear_pattern(pattern: str) -> int:
    """清除匹配模式的缓存"""
    try:
        client = get_redis_client()
        if client is None:
            return 0
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception:
        return 0
