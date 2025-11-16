# Memory Optimization Guide

## Problem
The application was exceeding the 512MB memory limit in production, causing instance failures.

## Root Causes

1. **Large ML Model Loading**: The AlephBERT sentence transformer model (~300-400MB) was loaded globally at startup
2. **Excessive Connection Pooling**: Database pool configured for 10 connections + 20 overflow (unnecessary for small instances)
3. **Batch Processing**: Tag encoding was processing all tags at once without batching

## Solutions Implemented

### 1. Lazy Model Loading
**Changed**: Model now loads only when semantic search is actually used, not at startup.

**Before** (routes.py):
```python
# Loaded at startup - always consumes memory
model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')
semantic_search_engine = SemanticSearchEngine(model)
```

**After** (routes.py):
```python
# Lazy-loaded only when needed
_model = None
_semantic_search_engine = None

def get_semantic_search_engine():
    global _model, _semantic_search_engine
    if _semantic_search_engine is None:
        _model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')
        _semantic_search_engine = SemanticSearchEngine(_model)
    return _semantic_search_engine
```

**Memory Savings**: ~350MB saved if semantic search is not used

### 2. Reduced Connection Pooling
**Changed**: Reduced database connection pool from 30 total connections to 5.

**Before** (config.py):
```python
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_MAX_OVERFLOW = 20
```

**After** (config.py):
```python
SQLALCHEMY_POOL_SIZE = 2
SQLALCHEMY_MAX_OVERFLOW = 3
SQLALCHEMY_POOL_RECYCLE = 300
SQLALCHEMY_POOL_PRE_PING = True
```

**Memory Savings**: ~10-20MB depending on connection overhead

### 3. Batch Processing for Tag Encoding
**Changed**: Process tags in batches of 10 instead of all at once.

**Memory Savings**: ~5-10MB during semantic search operations

## Additional Recommendations

### For Production Deployment

1. **Upgrade Instance Size** (Recommended)
   - If using Render/Heroku/Railway: Upgrade to at least 1GB RAM instance
   - Cost: Usually $5-10/month
   - This is the most reliable solution for ML-based applications

2. **Use External Model Hosting** (Advanced)
   - Host the model on a separate service (e.g., Hugging Face Inference API)
   - Keep your main app lightweight
   - Trade-off: Adds latency and external dependency

3. **Disable Semantic Search** (Temporary)
   - If budget is tight, disable semantic search feature temporarily
   - Users can still use text search and tag-based search
   - Add environment variable to control feature availability

4. **Add Memory Monitoring**
   ```python
   import psutil
   import os
   
   def log_memory_usage():
       process = psutil.Process(os.getpid())
       mem_info = process.memory_info()
       print(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")
   ```

### Environment Variables to Add

```bash
# .env
ENABLE_SEMANTIC_SEARCH=true  # Set to false to disable semantic search
MAX_MEMORY_MB=450  # Alert threshold
```

### Gunicorn Configuration

Create `gunicorn.conf.py`:
```python
# Optimize for low memory
workers = 1  # Single worker for 512MB instance
worker_class = 'sync'
worker_connections = 50
max_requests = 100  # Restart worker after 100 requests to prevent memory leaks
max_requests_jitter = 10
timeout = 120
preload_app = False  # Don't preload to save memory
```

Run with:
```bash
gunicorn --config gunicorn.conf.py app:app
```

## Memory Usage Estimates

| Component | Memory Usage |
|-----------|--------------|
| Flask + Dependencies | ~50-80 MB |
| Database Connections (2+3) | ~10-20 MB |
| AlephBERT Model (when loaded) | ~300-400 MB |
| Request Processing | ~20-50 MB |
| **Total (without model)** | ~80-150 MB |
| **Total (with model)** | ~380-550 MB |

## Testing Memory Usage Locally

```bash
# Install memory profiler
pip install memory-profiler psutil

# Run with memory monitoring
python -m memory_profiler app.py
```

## Monitoring in Production

Add this to your routes to track memory:
```python
import psutil
import os

@main.before_request
def log_memory():
    if current_app.debug:
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        current_app.logger.info(f"Memory: {mem_mb:.2f} MB")
```

## Conclusion

With these optimizations, the app should run within 512MB when semantic search is not actively used. However, for production use with semantic search, **upgrading to 1GB RAM is strongly recommended**.
