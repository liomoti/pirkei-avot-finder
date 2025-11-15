"""
Rate Limiting Module

Provides simple rate limiting functionality to prevent abuse
and manage server resources effectively.
"""

import time
from functools import wraps
from flask import request, jsonify, current_app
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """
    Simple in-memory rate limiter using token bucket algorithm.
    
    For production, consider using Redis-based solutions like Flask-Limiter.
    """
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if a request is allowed based on rate limits.
        
        Args:
            key: Unique identifier (e.g., IP address)
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if request is allowed, False otherwise
        """
        with self.lock:
            now = time.time()
            cutoff_time = now - window_seconds
            
            # Remove old requests outside the time window
            self.requests[key] = [
                req_time for req_time in self.requests[key] 
                if req_time > cutoff_time
            ]
            
            # Check if limit exceeded
            if len(self.requests[key]) >= max_requests:
                return False
            
            # Add current request
            self.requests[key].append(now)
            return True
    
    def get_remaining_requests(self, key: str, max_requests: int, window_seconds: int) -> int:
        """
        Get the number of remaining requests for a key.
        
        Args:
            key: Unique identifier
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Number of remaining requests
        """
        with self.lock:
            now = time.time()
            cutoff_time = now - window_seconds
            
            # Count recent requests
            recent_requests = [
                req_time for req_time in self.requests[key] 
                if req_time > cutoff_time
            ]
            
            return max(0, max_requests - len(recent_requests))


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Decorator to apply rate limiting to Flask routes.
    
    Args:
        max_requests: Maximum number of requests allowed per window
        window_seconds: Time window in seconds
        
    Example:
        @rate_limit(max_requests=5, window_seconds=60)
        def my_route():
            return "Hello"
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Use IP address as the key
            key = request.remote_addr or 'unknown'
            
            if not rate_limiter.is_allowed(key, max_requests, window_seconds):
                remaining = rate_limiter.get_remaining_requests(key, max_requests, window_seconds)
                current_app.logger.warning(
                    f'Rate limit exceeded for {key} on {request.endpoint}'
                )
                
                # Return Hebrew error message
                return jsonify({
                    'error': 'חרגת ממגבלת הבקשות. אנא נסה שוב בעוד מספר שניות.',
                    'message': f'מותרות {max_requests} בקשות כל {window_seconds} שניות.',
                    'remaining': remaining
                }), 429
            
            return f(*args, **kwargs)
        return wrapped
    return decorator
