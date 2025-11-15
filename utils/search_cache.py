"""
Search Cache Module

Provides simple caching for semantic search results to reduce
computational load and improve response times.
"""

import hashlib
import time
from typing import Optional, Any
from threading import Lock


class SearchCache:
    """
    Simple in-memory cache for search results.
    
    Uses LRU-like eviction when cache size exceeds maximum.
    For production, consider using Redis or Memcached.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize the cache.
        
        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cached items in seconds (default: 5 minutes)
        """
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.lock = Lock()
    
    def _generate_key(self, query: str) -> str:
        """
        Generate a cache key from a query string.
        
        Args:
            query: The search query
            
        Returns:
            MD5 hash of the normalized query
        """
        # Normalize query (lowercase, strip whitespace)
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def get(self, query: str) -> Optional[Any]:
        """
        Retrieve cached results for a query.
        
        Args:
            query: The search query
            
        Returns:
            Cached results if found and not expired, None otherwise
        """
        with self.lock:
            key = self._generate_key(query)
            
            if key not in self.cache:
                return None
            
            # Check if expired
            cached_time = self.access_times.get(key, 0)
            if time.time() - cached_time > self.ttl_seconds:
                # Remove expired entry
                del self.cache[key]
                del self.access_times[key]
                return None
            
            # Update access time
            self.access_times[key] = time.time()
            return self.cache[key]
    
    def set(self, query: str, results: Any) -> None:
        """
        Cache search results for a query.
        
        Args:
            query: The search query
            results: The search results to cache
        """
        with self.lock:
            key = self._generate_key(query)
            
            # Evict oldest entry if cache is full
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
            
            # Store results
            self.cache[key] = results
            self.access_times[key] = time.time()
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache size and other stats
        """
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl_seconds': self.ttl_seconds
            }


# Global cache instance
search_cache = SearchCache(max_size=100, ttl_seconds=300)
