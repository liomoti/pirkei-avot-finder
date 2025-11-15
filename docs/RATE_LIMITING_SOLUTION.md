# פתרון Rate Limiting - מערכת פרקי אבות

## סקירה כללית

מסמך זה מתאר את הפתרון המלא לבעיית Rate Limiting במערכת חיפוש פרקי אבות.

## הבעיות שזוהו

1. **חיפוש סמנטי יקר** - כל חיפוש סמנטי דורש:
   - קידוד של השאילתה באמצעות מודל AlephBERT
   - חישוב דמיון וקטורי מול כל המשניות במסד הנתונים
   - עיבוד תגיות ו-boosting

2. **אין הגבלת קצב** - משתמשים יכלו לשלוח בקשות ללא הגבלה

3. **אין Caching** - אותן שאילתות מחושבות שוב ושוב

## הפתרון המוצע

### 1. Rate Limiting (`utils/rate_limiter.py`)

מימוש פשוט של Token Bucket Algorithm:

```python
@rate_limit(max_requests=20, window_seconds=60)
def search_mishna():
    # ...
```

**הגדרות:**
- חיפוש רגיל: 20 בקשות לדקה
- חיפוש סמנטי: 10 בקשות לדקה (יקר יותר)

**תכונות:**
- שימוש ב-IP address כמזהה
- ניקוי אוטומטי של בקשות ישנות
- Thread-safe עם Lock
- הודעות שגיאה בעברית

### 2. Search Caching (`utils/search_cache.py`)

מטמון זיכרון פשוט לתוצאות חיפוש:

**הגדרות:**
- גודל מקסימלי: 100 שאילתות
- TTL: 5 דקות
- אלגוריתם: LRU-like eviction

**יתרונות:**
- מפחית עומס על המודל
- משפר זמני תגובה
- חוסך משאבי CPU

### 3. שיפורי Configuration (`config.py`)

הוספת הגדרות מרכזיות:

```python
RATE_LIMIT_ENABLED = True
RATE_LIMIT_SEARCH = 20
RATE_LIMIT_SEMANTIC = 10
RATE_LIMIT_WINDOW = 60
```

### 4. שיפור דף שגיאות (`templates/error.html`)

- עיצוב ידידותי יותר
- הודעות ברורות בעברית
- כפתור חזרה נוח

## איך זה עובד?

### תרשים זרימה - חיפוש סמנטי

```
1. משתמש שולח שאילתה
   ↓
2. בדיקת Rate Limit (10/דקה)
   ↓ (אם עבר)
3. בדיקת Cache
   ↓
4a. אם נמצא ב-Cache → החזר תוצאות
   ↓
4b. אם לא נמצא:
    - קידוד השאילתה
    - חיפוש במסד נתונים
    - שמירה ב-Cache
   ↓
5. החזרת תוצאות למשתמש
```

## שיפורים עתידיים אפשריים

### לסביבת Production:

1. **Redis-based Rate Limiting**
   ```bash
   pip install flask-limiter redis
   ```
   - מאפשר rate limiting בין מספר שרתים
   - יותר יעיל לסביבות גדולות

2. **Redis-based Caching**
   ```bash
   pip install redis
   ```
   - Cache משותף בין שרתים
   - Persistence של תוצאות

3. **CDN Caching**
   - Cloudflare או AWS CloudFront
   - Caching ברמת ה-HTTP

4. **Database Connection Pooling**
   - כבר מוגדר ב-`config.py`:
     ```python
     SQLALCHEMY_POOL_SIZE = 10
     SQLALCHEMY_MAX_OVERFLOW = 20
     ```

5. **Async Processing**
   - שימוש ב-Celery לחיפושים כבדים
   - תור עבודות עם Redis/RabbitMQ

## בדיקות

### בדיקת Rate Limiting:

```bash
# שלח 15 בקשות מהירות
for i in {1..15}; do
  curl -X POST http://localhost:5000/ \
    -d "action=search_semantic&semantic_query=test"
done
```

הבקשה ה-11 צריכה להחזיר שגיאה 429.

### בדיקת Cache:

```python
from utils.search_cache import search_cache

# בדיקת סטטיסטיקות
stats = search_cache.get_stats()
print(f"Cache size: {stats['size']}/{stats['max_size']}")
```

## Monitoring

### לוגים חשובים:

```python
# Rate limit exceeded
current_app.logger.warning(f'Rate limit exceeded for {key}')

# Cache hit/miss
current_app.logger.info(f'Cache hit for query: {query}')
current_app.logger.info(f'Cache miss - performing semantic search')
```

### מדדים למעקב:

1. **Rate Limit Hits** - כמה פעמים משתמשים חרגו מהמגבלה
2. **Cache Hit Rate** - אחוז הפגיעות ב-Cache
3. **Average Response Time** - זמן תגובה ממוצע
4. **Semantic Search Count** - מספר חיפושים סמנטיים

## סיכום

הפתרון מספק:
- ✅ הגנה מפני שימוש יתר
- ✅ שיפור ביצועים משמעותי
- ✅ חוויית משתמש טובה יותר
- ✅ קל להרחבה ושדרוג

הקוד פשוט ומודולרי, ומאפשר מעבר קל לפתרונות מתקדמים יותר בעתיד.
