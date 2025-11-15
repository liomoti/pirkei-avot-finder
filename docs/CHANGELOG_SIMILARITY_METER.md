# Change Log - מד דמיון לחיפוש AI

## תאריך: 7 בנובמבר 2025

### תכונה חדשה: מד דמיון לתוצאות חיפוש AI

#### שינויים בקוד:

##### 1. `routes.py`
**שורות 201-217** - הוספת similarity_score לאובייקטי Mishna:
```python
# Filter results and attach similarity scores
results = []
borderline_results = []

for distance, mishna in candidates:
    if distance <= cutoff_distance:
        # Attach similarity score to mishna object
        mishna.similarity_score = distance
        results.append(mishna)
        # ... logging
```

**שורות 234-237** - הוספת דגל is_semantic_search:
```python
search_query = None
is_semantic_search = False
if request.method == 'POST':
    if action == 'search_free_text':
        search_query = mishna_form.text.data
    elif action == 'search_semantic':
        search_query = request.form.get('semantic_query', '').strip()
        is_semantic_search = True
```

**שורה 245** - העברת is_semantic_search לתבנית:
```python
return render_template('index.html',
                       # ... other parameters
                       is_semantic_search=is_semantic_search,
                       # ... other parameters
                       )
```

##### 2. `templates/index.html`
**שורות 458-490** - הוספת מד הדמיון:
```html
<!-- Similarity Score (AI Search Only) -->
{% if is_semantic_search and result.similarity_score is defined %}
<div class="mb-4">
    <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-bold text-gray-700 flex items-center">
            <svg class="w-4 h-4 ml-1 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
            </svg>
            רמת התאמה:
        </span>
        <span class="text-sm font-semibold" style="color: ...">
            <!-- תווית דמיון -->
        </span>
    </div>
    <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden shadow-inner">
        <div class="h-full rounded-full transition-all duration-500 flex items-center justify-end px-1"
            style="width: {{ ((0.72 - result.similarity_score) / 0.22 * 100) | round }}%; ...">
            <span class="text-xs font-bold text-white drop-shadow">{{ ((0.72 - result.similarity_score) / 0.22 * 100) | round }}%</span>
        </div>
    </div>
</div>
{% endif %}
```

#### קבצים חדשים:

1. **similarity_meter_demo.html** - דף דמו להצגת המד בכל הדרגות
2. **SIMILARITY_METER_SUMMARY.md** - סיכום טכני של השינויים
3. **FEATURE_SIMILARITY_METER.md** - תיעוד למשתמש הקצה
4. **CHANGELOG_SIMILARITY_METER.md** - מסמך זה

#### לוגיקת המד:

**טווח Distance**: 0.50 (מצוין) - 0.72 (נמוך)

**5 דרגות**:
- מצוין: distance < 0.55 (ירוק)
- טוב מאוד: 0.55 ≤ distance < 0.58 (ירוק)
- טוב: 0.58 ≤ distance < 0.62 (צהוב)
- בינוני: 0.62 ≤ distance < 0.66 (צהוב)
- נמוך: distance ≥ 0.66 (כתום)

**חישוב אחוזים**:
```
percentage = ((0.72 - distance) / 0.22) × 100
```

#### בדיקות שבוצעו:

✅ קומפילציה של routes.py - הצליחה
✅ בדיקת לוגיקת החישוב - עברה
✅ יצירת דף דמו - הושלמה
✅ תיעוד - הושלם

#### השפעה על ביצועים:

- **זניחה** - רק הוספת attribute אחד לכל אובייקט Mishna
- **אין שאילתות נוספות למסד הנתונים**
- **אין עיבוד נוסף בצד השרת**

#### תאימות לאחור:

✅ **מלאה** - השינויים לא משפיעים על:
- חיפוש לפי פרק ומשנה
- חיפוש טקסט חופשי
- חיפוש לפי תגיות
- תוצאות חיפוש AI קיימות (פשוט מוסיפים מידע)

#### הערות למפתחים:

1. המד מופיע רק כאשר `is_semantic_search=True` ו-`result.similarity_score` מוגדר
2. ה-similarity_score הוא ה-distance מחישוב הווקטורים
3. ניתן לשנות את הסף של הדרגות ב-template (שורות 467-478)
4. ניתן לשנות את הצבעים ב-template (שורות 483-486)

#### TODO עתידי (אופציונלי):

- [ ] הוסף tooltip עם הסבר על המד
- [ ] אפשר למשתמש לסנן תוצאות לפי רמת התאמה מינימלית
- [ ] הוסף אנימציה כשהמד נטען
- [ ] שמור העדפות משתמש לגבי הצגת המד

---

**סטטוס**: ✅ הושלם ומוכן לשימוש
**גרסה**: 1.0.0
**מפתח**: Kiro AI Assistant
