# דוגמאות שימוש - Rate Limiting & Caching

## 🎯 דוגמאות בסיסיות

### 1. הוספת Rate Limiting לRoute חדש

```python
from utils.rate_limiter import rate_limit

@main.route('/api/search', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)  # 30 בקשות לדקה
def api_search():
    query = request.json.get('query')
    results = perform_search(query)
    return jsonify(results)
```

### 2. שימוש ב-Cache

```python
from utils.search_cache import search_cache

def my_expensive_function(query):
    # בדוק אם יש ב-Cache
    cached_result = search_cache.get(query)
    if cached_result is not None:
        return cached_result
    
    # בצע חישוב יקר
    result = expensive_computation(query)
    
    # שמור ב-Cache
    search_cache.set(query, result)
    
    return result
```

### 3. Rate Limiting ידני (בלי Decorator)

```python
from utils.rate_limiter import rate_limiter
from flask import request, jsonify

@main.route('/api/data')
def get_data():
    key = request.remote_addr
    
    # בדוק אם מותר
    if not rate_limiter.is_allowed(key, max_requests=10, window_seconds=60):
        return jsonify({
            'error': 'Too many requests',
            'retry_after': 60
        }), 429
    
    # המשך עם הלוגיקה הרגילה
    return jsonify({'data': 'some data'})
```

## 🔧 דוגמאות מתקדמות

### 4. Rate Limiting שונה למשתמשים רשומים

```python
from utils.rate_limiter import rate_limiter
from flask import session

@main.route('/search')
def search():
    # משתמשים רשומים מקבלים יותר בקשות
    if session.get('access_token'):
        max_requests = 50  # משתמשים רשומים
    else:
        max_requests = 20  # אורחים
    
    key = request.remote_addr
    if not rate_limiter.is_allowed(key, max_requests, 60):
        return render_template('error.html', 
                             error='חרגת ממגבלת הבקשות')
    
    # המשך...
```

### 5. Cache עם TTL מותאם אישית

```python
from utils.search_cache import SearchCache

# צור Cache עם הגדרות מותאמות
custom_cache = SearchCache(
    max_size=50,      # 50 פריטים בלבד
    ttl_seconds=600   # 10 דקות
)

def cached_function(param):
    result = custom_cache.get(param)
    if result is None:
        result = compute_result(param)
        custom_cache.set(param, result)
    return result
```

### 6. ניקוי Cache אוטומטי

```python
from utils.search_cache import search_cache
from flask import current_app

@main.route('/admin/clear-cache', methods=['POST'])
@login_is_required
def clear_cache():
    search_cache.clear()
    current_app.logger.info('Cache cleared by admin')
    return jsonify({'message': 'Cache cleared successfully'})
```

### 7. סטטיסטיקות Cache

```python
from utils.search_cache import search_cache

@main.route('/admin/cache-stats')
@login_is_required
def cache_stats():
    stats = search_cache.get_stats()
    
    return jsonify({
        'cache_size': stats['size'],
        'max_size': stats['max_size'],
        'usage_percent': (stats['size'] / stats['max_size']) * 100,
        'ttl_seconds': stats['ttl_seconds']
    })
```

### 8. Rate Limiting עם Whitelist

```python
from utils.rate_limiter import rate_limiter

WHITELISTED_IPS = ['127.0.0.1', '192.168.1.100']

@main.route('/api/endpoint')
def endpoint():
    ip = request.remote_addr
    
    # דלג על Rate Limiting ל-IPs מורשים
    if ip not in WHITELISTED_IPS:
        if not rate_limiter.is_allowed(ip, 10, 60):
            return jsonify({'error': 'Rate limit exceeded'}), 429
    
    return jsonify({'data': 'success'})
```

## 📊 דוגמאות ניטור

### 9. לוג מפורט של Rate Limiting

```python
from flask import current_app
from utils.rate_limiter import rate_limiter

@main.route('/search')
def search():
    key = request.remote_addr
    remaining = rate_limiter.get_remaining_requests(key, 20, 60)
    
    current_app.logger.info(
        f'Search request from {key}, '
        f'remaining requests: {remaining}/20'
    )
    
    if not rate_limiter.is_allowed(key, 20, 60):
        current_app.logger.warning(f'Rate limit exceeded for {key}')
        return render_template('error.html', 
                             error='חרגת ממגבלת הבקשות')
    
    # המשך...
```

### 10. מדידת Cache Hit Rate

```python
from utils.search_cache import search_cache

cache_hits = 0
cache_misses = 0

def search_with_metrics(query):
    global cache_hits, cache_misses
    
    result = search_cache.get(query)
    
    if result is not None:
        cache_hits += 1
        hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
        current_app.logger.info(f'Cache hit! Hit rate: {hit_rate:.1f}%')
        return result
    else:
        cache_misses += 1
        result = perform_search(query)
        search_cache.set(query, result)
        return result
```

## 🎨 דוגמאות UI

### 11. הצגת מגבלות למשתמש

```html
<!-- בתבנית HTML -->
<div class="rate-limit-info">
    <p>מותרות {{ max_requests }} בקשות לדקה</p>
    <p>נותרו לך {{ remaining_requests }} בקשות</p>
</div>
```

```python
# ב-route
from utils.rate_limiter import rate_limiter

@main.route('/')
def index():
    key = request.remote_addr
    remaining = rate_limiter.get_remaining_requests(key, 20, 60)
    
    return render_template('index.html',
                         max_requests=20,
                         remaining_requests=remaining)
```

### 12. Progress Bar לCache

```html
<!-- בתבנית HTML -->
<div class="cache-status">
    <div class="progress-bar">
        <div class="progress-fill" 
             style="width: {{ cache_usage }}%">
        </div>
    </div>
    <p>Cache: {{ cache_size }}/{{ cache_max }}</p>
</div>
```

```python
# ב-route
from utils.search_cache import search_cache

@main.route('/admin/dashboard')
@login_is_required
def dashboard():
    stats = search_cache.get_stats()
    usage = (stats['size'] / stats['max_size']) * 100
    
    return render_template('dashboard.html',
                         cache_size=stats['size'],
                         cache_max=stats['max_size'],
                         cache_usage=usage)
```

## 🧪 דוגמאות בדיקה

### 13. בדיקת Rate Limiting עם pytest

```python
import pytest
from app import app

def test_rate_limiting():
    client = app.test_client()
    
    # שלח 20 בקשות (המגבלה)
    for i in range(20):
        response = client.post('/search', data={'query': 'test'})
        assert response.status_code == 200
    
    # הבקשה ה-21 צריכה להיחסם
    response = client.post('/search', data={'query': 'test'})
    assert response.status_code == 429
```

### 14. בדיקת Cache

```python
from utils.search_cache import SearchCache

def test_cache():
    cache = SearchCache(max_size=10, ttl_seconds=60)
    
    # בדיקת Cache miss
    assert cache.get('test') is None
    
    # שמירה ב-Cache
    cache.set('test', 'result')
    
    # בדיקת Cache hit
    assert cache.get('test') == 'result'
```

## 💡 טיפים

### טיפ 1: שימוש ב-Cache לפונקציות יקרות
```python
from functools import wraps
from utils.search_cache import search_cache

def cached(ttl=300):
    """Decorator לCaching אוטומטי"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # צור מפתח מהארגומנטים
            key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            result = search_cache.get(key)
            if result is None:
                result = f(*args, **kwargs)
                search_cache.set(key, result)
            
            return result
        return wrapper
    return decorator

@cached(ttl=600)
def expensive_function(param1, param2):
    # חישוב יקר...
    return result
```

### טיפ 2: Rate Limiting דינמי
```python
import datetime

def get_rate_limit():
    """החזר מגבלה דינמית לפי שעה"""
    hour = datetime.datetime.now().hour
    
    # שעות שיא (9-17): מגבלה נמוכה יותר
    if 9 <= hour <= 17:
        return 10
    # שעות רגילות: מגבלה גבוהה יותר
    else:
        return 30

@main.route('/search')
def search():
    limit = get_rate_limit()
    if not rate_limiter.is_allowed(request.remote_addr, limit, 60):
        return error_response()
    # המשך...
```

---

**עוד שאלות?** ראה את התיעוד המלא ב-`docs/RATE_LIMITING_SOLUTION.md`
