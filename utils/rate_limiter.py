"""Simple rate limiter for Flask routes."""
from functools import wraps
from flask import request, render_template, current_app
from time import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""
    
    def __init__(self):
        self.requests = defaultdict(deque)
    
    def is_allowed(self, key, max_requests, window_seconds):
        """Check if a request is allowed based on rate limits."""
        now = time()
        cutoff = now - window_seconds
        
        # Remove old requests outside the window
        while self.requests[key] and self.requests[key][0] < cutoff:
            self.requests[key].popleft()
        
        # Check if limit exceeded
        if len(self.requests[key]) >= max_requests:
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True
    
    def cleanup_old_entries(self):
        """Periodically cleanup old entries to prevent memory leaks."""
        now = time()
        keys_to_delete = []
        
        for key, timestamps in self.requests.items():
            # If the last request was more than 1 hour ago, remove the key
            if timestamps and (now - timestamps[-1]) > 3600:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(max_requests=20, window_seconds=60):
    """
    Decorator to rate limit a Flask route.
    
    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Use IP address as the key
            key = request.remote_addr or 'unknown'
            
            if not rate_limiter.is_allowed(key, max_requests, window_seconds):
                current_app.logger.warning(f'Rate limit exceeded for {key}')
                return render_template('error.html', 
                                     error="חרגת ממגבלת הבקשות. אנא נסה שוב בעוד מספר שניות.")
            
            return f(*args, **kwargs)
        return wrapper
    return decorator
