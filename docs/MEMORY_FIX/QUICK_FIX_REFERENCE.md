# Quick Fix Reference - Memory Issue

## 🔴 Problem
```
Instance failed: Ran out of memory (used over 512MB)
```

## ✅ Solution
Lazy-load the ML model instead of loading at startup.

## 📋 What Changed

| File | Change | Memory Saved |
|------|--------|--------------|
| `routes.py` | Lazy model loading | ~350 MB |
| `config.py` | Reduced DB pool (30→5) | ~15 MB |
| `utils/semantic_search.py` | Batch processing | ~10 MB |

## 🚀 Deploy Now

```bash
# 1. Commit
git add .
git commit -m "Fix: Optimize memory for 512MB limit"
git push

# 2. Update start command (if needed)
gunicorn --config gunicorn.conf.py app:app

# 3. Set environment
GUNICORN_WORKERS=1
```

## 📊 Expected Results

- **Before**: 450-550 MB at startup ❌
- **After**: 80-150 MB at startup ✅
- **When semantic search used**: 380-500 MB ⚠️

## ✔️ Verify Success

Check logs after deployment:
- ✅ "Loading AlephBERT model" should NOT appear at startup
- ✅ Should only appear when semantic search is used
- ✅ No "out of memory" errors

## 🆘 Still Having Issues?

### Quick Fixes:
1. **Verify worker count**: `GUNICORN_WORKERS=1`
2. **Check memory**: `python scripts/check_memory.py`
3. **Upgrade instance**: 1GB RAM ($5-10/month) - RECOMMENDED

### Emergency Fix:
Disable semantic search temporarily:
```python
# In routes.py, comment out:
# elif action == 'search_semantic':
#     ... (entire block)
```

## 📚 More Info

- `MEMORY_FIX_SUMMARY.md` - Complete overview
- `DEPLOYMENT_CHECKLIST.md` - Step-by-step guide
- `docs/MEMORY_OPTIMIZATION.md` - Technical details

---
**TL;DR**: Model now loads only when needed. Deploy and monitor. Upgrade to 1GB if issues persist.
