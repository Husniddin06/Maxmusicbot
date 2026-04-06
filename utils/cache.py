import time
from typing import Any, Optional, Dict, Tuple

_cache: Dict[str, Tuple[Any, float]] = {}
CACHE_TTL = 3600

def get_cache(key: str) -> Optional[Any]:
    if key in _cache:
        value, expires = _cache[key]
        if time.time() < expires:
            return value
        del _cache[key]
    return None

def set_cache(key: str, value: Any, ttl: int = CACHE_TTL):
    _cache[key] = (value, time.time() + ttl)

def clear_expired():
    now = time.time()
    for k in [k for k, (_, e) in _cache.items() if now >= e]:
        del _cache[k]
