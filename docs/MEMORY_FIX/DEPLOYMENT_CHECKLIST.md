# Deployment Checklist - Memory Optimization

## Changes Made to Fix Memory Issues

✅ **1. Lazy Model Loading** (routes.py)
   - Model now loads only when semantic search is used
   - Saves ~350MB at startup

✅ **2. Reduced Database Connection Pool** (config.py)
   - Changed from 30 connections to 5 total
   - Saves ~10-20MB

✅ **3. Batch Processing** (utils/semantic_search.py)
   - Tags encoded in batches of 10
   - Reduces peak memory usage

✅ **4. Added Gunicorn Config** (gunicorn.conf.py)
   - Optimized for low-memory deployment
   - Single worker configuration

✅ **5. Added Memory Monitoring** (requirements.txt)
   - Added psutil for memory tracking

## Deployment Steps

### Option A: Deploy with Current Changes (512MB Instance)

1. **Update your deployment platform configuration:**
   ```bash
   # If using Render/Railway/Heroku, update start command:
   gunicorn --config gunicorn.conf.py app:app
   ```

2. **Set environment variables:**
   ```bash
   GUNICORN_WORKERS=1
   PORT=5000
   ```

3. **Deploy and monitor:**
   - Watch logs for "Loading AlephBERT model" message
   - This should only appear when someone uses semantic search
   - Monitor memory usage in your platform dashboard

### Option B: Upgrade Instance (Recommended)

1. **Upgrade to 1GB RAM instance**
   - Render: Upgrade to Starter plan ($7/month)
   - Railway: Upgrade to Hobby plan ($5/month)
   - Heroku: Upgrade to Hobby dyno ($7/month)

2. **Update worker count:**
   ```bash
   GUNICORN_WORKERS=2
   ```

3. **Deploy with confidence**
   - Model can stay in memory
   - Better performance for semantic search

### Option C: Disable Semantic Search (Temporary)

If you need to stay on 512MB and can't use semantic search:

1. **Comment out semantic search in routes.py:**
   ```python
   # elif action == 'search_semantic':
   #     # ... entire semantic search block
   ```

2. **Hide semantic search UI in templates/index.html**

3. **Deploy**
   - App will use ~80-150MB
   - Only text and tag search available

## Testing Before Deployment

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test locally with gunicorn
gunicorn --config gunicorn.conf.py app:app

# 3. Test semantic search
# Open browser and try a semantic search query
# Watch terminal for "Loading AlephBERT model" message

# 4. Monitor memory (optional)
# In another terminal:
python -c "import psutil; import time; 
while True: 
    mem = psutil.Process().memory_info().rss / 1024 / 1024; 
    print(f'Memory: {mem:.2f} MB'); 
    time.sleep(5)"
```

## Expected Memory Usage

| Scenario | Memory Usage |
|----------|--------------|
| App startup (no semantic search used) | 80-150 MB ✅ |
| After first semantic search | 380-550 MB ⚠️ |
| Multiple concurrent users | 450-600 MB ⚠️ |

## Troubleshooting

### Still Getting Memory Errors?

1. **Check worker count:**
   ```bash
   echo $GUNICORN_WORKERS
   # Should be 1 for 512MB instance
   ```

2. **Verify lazy loading is working:**
   - Check logs after deployment
   - "Loading AlephBERT model" should NOT appear at startup
   - Should only appear when semantic search is used

3. **Check for memory leaks:**
   - Add this to routes.py for debugging:
   ```python
   import psutil
   import os
   
   @main.before_request
   def log_memory():
       process = psutil.Process(os.getpid())
       mem_mb = process.memory_info().rss / 1024 / 1024
       current_app.logger.info(f"Memory: {mem_mb:.2f} MB")
   ```

4. **Consider disabling features:**
   - Disable semantic search temporarily
   - Reduce rate limit cache size
   - Reduce max_candidates in semantic search (from 30 to 15)

## Monitoring After Deployment

Watch for these in your logs:
- ✅ "Loading AlephBERT model" - only when semantic search is used
- ⚠️ "Memory usage: XXX MB" - should stay under 450MB most of the time
- ❌ "Ran out of memory" - upgrade instance if this appears

## Recommended Next Steps

1. **Deploy with current optimizations**
2. **Monitor for 24-48 hours**
3. **If memory issues persist → Upgrade to 1GB instance**
4. **If budget is tight → Disable semantic search temporarily**

## Support

See `docs/MEMORY_OPTIMIZATION.md` for detailed technical information.
