"""
Tests for Rate Limiting functionality

Run with: python tests/test_rate_limiting.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from utils.rate_limiter import RateLimiter
from utils.search_cache import SearchCache


def test_rate_limiter_basic():
    """Test basic rate limiting functionality."""
    limiter = RateLimiter()
    
    # Should allow first 5 requests
    for i in range(5):
        assert limiter.is_allowed('test_key', 5, 10), f"Request {i+1} should be allowed"
    
    # Should block 6th request
    assert not limiter.is_allowed('test_key', 5, 10), "6th request should be blocked"
    
    print("✓ Basic rate limiting works")


def test_rate_limiter_window():
    """Test that rate limit resets after time window."""
    limiter = RateLimiter()
    
    # Fill up the limit
    for i in range(3):
        limiter.is_allowed('test_key2', 3, 2)
    
    # Should be blocked
    assert not limiter.is_allowed('test_key2', 3, 2), "Should be blocked"
    
    # Wait for window to expire
    time.sleep(2.1)
    
    # Should be allowed again
    assert limiter.is_allowed('test_key2', 3, 2), "Should be allowed after window expires"
    
    print("✓ Time window reset works")


def test_rate_limiter_different_keys():
    """Test that different keys are tracked separately."""
    limiter = RateLimiter()
    
    # Fill limit for key1
    for i in range(5):
        limiter.is_allowed('key1', 5, 10)
    
    # key1 should be blocked
    assert not limiter.is_allowed('key1', 5, 10), "key1 should be blocked"
    
    # key2 should still be allowed
    assert limiter.is_allowed('key2', 5, 10), "key2 should be allowed"
    
    print("✓ Different keys tracked separately")


def test_search_cache_basic():
    """Test basic cache functionality."""
    cache = SearchCache(max_size=10, ttl_seconds=60)
    
    # Cache miss
    assert cache.get('test query') is None, "Should be cache miss"
    
    # Set value
    cache.set('test query', ['result1', 'result2'])
    
    # Cache hit
    results = cache.get('test query')
    assert results == ['result1', 'result2'], "Should return cached results"
    
    print("✓ Basic caching works")


def test_search_cache_normalization():
    """Test that cache normalizes queries."""
    cache = SearchCache(max_size=10, ttl_seconds=60)
    
    # Set with one format
    cache.set('Test Query', ['result'])
    
    # Get with different format (should still hit)
    results = cache.get('test query')
    assert results == ['result'], "Should normalize and find cached result"
    
    # With extra whitespace
    results = cache.get('  test query  ')
    assert results == ['result'], "Should handle whitespace"
    
    print("✓ Query normalization works")


def test_search_cache_expiration():
    """Test that cache entries expire."""
    cache = SearchCache(max_size=10, ttl_seconds=1)
    
    # Set value
    cache.set('test', ['result'])
    
    # Should be available immediately
    assert cache.get('test') is not None, "Should be cached"
    
    # Wait for expiration
    time.sleep(1.1)
    
    # Should be expired
    assert cache.get('test') is None, "Should be expired"
    
    print("✓ Cache expiration works")


def test_search_cache_eviction():
    """Test that cache evicts old entries when full."""
    cache = SearchCache(max_size=3, ttl_seconds=60)
    
    # Fill cache
    cache.set('query1', ['result1'])
    time.sleep(0.1)  # Ensure different timestamps
    cache.set('query2', ['result2'])
    time.sleep(0.1)
    cache.set('query3', ['result3'])
    
    # All should be cached
    assert cache.get('query1') is not None
    assert cache.get('query2') is not None
    assert cache.get('query3') is not None
    
    # Add one more (should evict oldest)
    time.sleep(0.1)
    cache.set('query4', ['result4'])
    
    # query1 should be evicted (oldest)
    assert cache.get('query1') is None, "Oldest entry should be evicted"
    assert cache.get('query4') is not None, "New entry should be cached"
    
    print("✓ Cache eviction works")


def test_cache_stats():
    """Test cache statistics."""
    cache = SearchCache(max_size=10, ttl_seconds=60)
    
    cache.set('q1', ['r1'])
    cache.set('q2', ['r2'])
    
    stats = cache.get_stats()
    assert stats['size'] == 2, "Should show 2 cached items"
    assert stats['max_size'] == 10, "Should show max size"
    assert stats['ttl_seconds'] == 60, "Should show TTL"
    
    print("✓ Cache statistics work")


if __name__ == '__main__':
    print("Running Rate Limiting Tests...\n")
    
    test_rate_limiter_basic()
    test_rate_limiter_window()
    test_rate_limiter_different_keys()
    
    print("\nRunning Cache Tests...\n")
    
    test_search_cache_basic()
    test_search_cache_normalization()
    test_search_cache_expiration()
    test_search_cache_eviction()
    test_cache_stats()
    
    print("\n✅ All tests passed!")
