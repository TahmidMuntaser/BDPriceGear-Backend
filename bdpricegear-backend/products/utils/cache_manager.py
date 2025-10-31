import hashlib
import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("cache_manager")

class SimpleCache:
    def __init__(self, default_ttl: int = 300):  # 5 min
        self.cache: Dict[str, Dict] = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, product: str) -> str:
        # generate cache key 
        return hashlib.md5(product.lower().strip().encode()).hexdigest()
    
    def get(self, product: str) -> Optional[Any]:
        # get data from cache
        key = self._generate_key(product)
        
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        current_time = time.time()
        
        # Check if expired
        if current_time > entry['expires_at']:
            del self.cache[key]
            return None
            
        logger.info(f"Cache hit for product: {product}")
        return entry['data']
    
    def set(self, product: str, data: Any, ttl: Optional[int] = None) -> None:
        #  Store data in cache 
        key = self._generate_key(product)
        ttl = ttl or self.default_ttl
        
        self.cache[key] = {
            'data': data,
            'expires_at': time.time() + ttl,
        }
        
        logger.info(f"Cache set for product: {product}")
    
    def clear_expired(self) -> int:
        # clean up (expired)
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
            
        return len(expired_keys)

# Global cache instance
price_cache = SimpleCache(default_ttl=300)  # 5 min cache