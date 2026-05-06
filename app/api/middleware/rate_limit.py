import time
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.infrastructure.redis_client import get_redis

async def rate_limit(request: Request, limit: int, window: int):
    """
    Basit Redis tabanlı IP rate limiter.
    limit: maksimum istek sayısı
    window: saniye cinsinden süre
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    path = request.url.path
    key = f"rate_limit:{client_ip}:{path}"
    
    redis = get_redis()
    
    current = await redis.get(key)
    if current and int(current) >= limit:
        raise HTTPException(status_code=429, detail="Too Many Requests")
        
    pipe = redis.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, window)
    await pipe.execute()
    return True

def rate_limit_dependency(limit: int, window: int):
    async def _dependency(request: Request):
        await rate_limit(request, limit, window)
    return _dependency
