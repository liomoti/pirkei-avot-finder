# מ-Flask Monolith ל-AWS Serverless: מיגרציה של אפליקציית חיפוש בעברית

*איך פירקתי אפליקציית Flask/Gunicorn לפונקציות Lambda, החלפתי Jinja2 ב-Alpine.js, והוספתי חיפוש סמנטי מבוסס AI — הכל תוך שמירה על אותו בסיס נתונים וללא זמן השבתה.*

---

## מבוא

[Pirkei Avot Finder](https://pirkei-avot.online) היא אפליקציית אינטרנט בעברית לחיפוש ולימוד משניות מפרקי אבות. האפליקציה תומכת בחיפוש רב-מודאלי: ניווט לפי פרק ומשנה, חיפוש טקסט מדויק, סינון לפי תגיות, וחיפוש סמנטי מבוסס AI שמבין את *המשמעות* של שאילתות בעברית.

האפליקציה התחילה כ-Flask monolith שרץ על Render. היא עבדה, אבל היו לה מגבלות סקלביליות, בעיות cold start בתוכנית החינמית, וארכיטקטורה צמודה שהקשתה על פיתוח והתפתחות. מאמר זה מתאר את המעבר המלא לארכיטקטורת serverless על AWS באמצעות Lambda, API Gateway, S3, CloudFront, Cognito ו-Bedrock.

---

## הארכיטקטורה המקורית

ה-monolith היה אפליקציית Flask/Gunicorn סטנדרטית:

![Monolith Architecture](monolith-architecture.png)

**Stack:**
- **Runtime**: Flask + Gunicorn על Render (free tier)
- **Templates**: Jinja2 server-side rendering
- **Database**: PostgreSQL על Supabase
- **Auth**: Supabase Auth (email/password למנהלים)
- **ORM**: Flask-SQLAlchemy
- **Semantic Search**: Lambda נפרד על AWS מאחורי API Gateway, שקורא ל-Bedrock Knowledge Base

**נקודות כאב:**
- ה-free tier של Render כיבה את השרת אחרי חוסר פעילות, מה שגרם ל-cold starts של 30+ שניות
- ה-monolith טיפל בהכל: routing, templates, שאילתות לבסיס הנתונים, אימות, וקריאות API לחיפוש הסמנטי
- סקלביליות משמעותה הגדלת כל האפליקציה, גם אם רק תעבורת החיפוש עלתה
- ה-Jinja2 templates היו צמודים ל-Flask — אין אפשרות ל-CDN caching על HTML
- החיפוש הסמנטי כבר היה על AWS, מה שיצר ארכיטקטורה מפוצלת

---

## היעד: Serverless מלא על AWS

המטרה הייתה להעביר הכל ל-AWS תוך שמירה על בסיס הנתונים הקיים ב-Supabase ושמירה על התנהגות זהה מצד המשתמש.

![Serverless Architecture](serverless-architecture.png)

**Stack חדש:**

| שכבה | טכנולוגיה |
|---|---|
| Frontend | Static HTML + Alpine.js 3.x + Tailwind CSS 2.x, מוגש מ-S3 |
| CDN | CloudFront עם דומיין מותאם (`pirkei-avot.online`) ותעודת ACM |
| API | API Gateway HTTP API עם Cognito JWT authorizer |
| Compute | 6 פונקציות AWS Lambda (Python 3.12) |
| Database | PostgreSQL על Supabase (ללא שינוי, דרך pgbouncer pooler על port 6543) |
| Auth | Amazon Cognito User Pool (email/password, הרשמה עצמית) |
| AI Search | Bedrock Knowledge Base + Amazon Nova Pro LLM reranking |
| IaC | AWS SAM (`template.yaml`) |

---

## החלטות ארכיטקטוניות

### למה לא פשוט containerization?

המיגרציה הפשוטה ביותר הייתה לשים את אפליקציית ה-Flask ב-Docker container על ECS או App Runner. בחרתי ב-Lambda מכמה סיבות:

1. **עלות**: לאפליקציה יש תעבורה לא אחידה — בעיקר שקטה עם פיקים מדי פעם בחיפוש. מודל ה-pay-per-invocation של Lambda זול משמעותית מ-container שרץ כל הזמן.
2. **סקלביליות עצמאית**: לחיפוש, לניהול ולאימות יש דפוסי תעבורה שונים מאוד. פונקציות Lambda נפרדות מתרחבות באופן עצמאי.
3. **רדיוס פגיעה קטן יותר**: באג ב-admin handler לא משפיע על החיפוש. לכל פונקציה יש הרשאות IAM, הקצאת זיכרון ו-timeout משלה.
4. **החיפוש הסמנטי כבר היה על Lambda**: חצי מהארכיטקטורה כבר הייתה serverless. העברת השאר ביטלה את הפיצול.

### למה להשאיר את Supabase PostgreSQL?

לבסיס הנתונים לא היו בעיות. Supabase מספקת instance מנוהל של PostgreSQL עם pgbouncer connection pooler מובנה על port 6543. ה-pooler הזה קריטי ל-Lambda — כל Lambda container מחזיק בדיוק חיבור אחד לבסיס הנתונים (`pool_size=1`), וה-pooler מרבב מאות חיבורים מקבילים של Lambda על מספר קטן יותר של חיבורים בפועל לבסיס הנתונים.

מעבר ל-RDS היה מוסיף עלות ומורכבות ללא תועלת. הנתונים נשארים במקומם.

### למה Alpine.js ולא React/Vue?

ה-Jinja2 templates המקוריים היו פשוטים יחסית — טפסי חיפוש, כרטיסי תוצאות, בחירת תגיות ופאנל ניהול. Alpine.js מספק בדיוק מספיק ריאקטיביות למקרה הזה:

- Inline ב-HTML (ללא build step, ללא bundler, ללא node_modules)
- נפח זעיר (~15KB)
- תחביר דקלרטיבי שממפה באופן טבעי למבנה ה-templates הקיים
- עובד מצוין עם Tailwind CSS דרך CDN

ה-frontend הוא באמת סטטי — ללא server-side rendering, ללא build pipeline. רק קבצי HTML שמוגשים מ-S3.

---

## המיגרציה: צעד אחר צעד

### שלב 1: Shared Lambda Layer

המשימה הראשונה הייתה חילוץ קוד משותף שכל פונקציות ה-Lambda יצטרכו. ב-monolith, Flask-SQLAlchemy סיפק את ה-ORM. ב-Lambda אין Flask — אז המודלים הועברו ל-SQLAlchemy רגיל עם `declarative_base()`.

ה-shared layer (`layers/shared/`) מכיל:

```
layers/shared/
├── models.py          # SQLAlchemy models (Mishna, Tag, Category, SiteSetting, UserFavorite, AiSearchLog)
├── db.py              # Engine + session factory (module-level initialization)
├── response.py        # API Gateway response helpers (success_response, error_response, serialize_mishna)
├── text_utils.py      # Hebrew niqqud removal (U+0591–U+05C7)
├── constants.py       # ALLOWED_CHAPTERS mapping (6 chapters, Hebrew letter keys)
└── requirements.txt   # sqlalchemy, psycopg2-binary
```

השינוי המרכזי ב-`db.py` הוא אתחול ברמת המודול. ה-database engine נוצר *מחוץ* לפונקציית ה-handler, כך שהוא נשמר בין invocations חמים של Lambda:

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ['DATABASE_URL']

engine = create_engine(
    DATABASE_URL,
    pool_size=1,          # חיבור אחד לכל Lambda container
    max_overflow=0,       # לעולם לא ליצור חיבורים נוספים
    pool_pre_ping=True,   # לאמת חיבור לפני שימוש
    pool_recycle=300,      # לרענן כל 5 דקות
    connect_args={'sslmode': 'require'}
)

Session = sessionmaker(bind=engine)
```

זו אופטימיזציה סטנדרטית ל-Lambda — cold starts יוצרים את ה-engine, invocations חמים משתמשים בו מחדש.


### שלב 2: פירוק לפונקציות Lambda

ה-routes של ה-monolith פוצלו לשש פונקציות Lambda לפי תחום:

| Lambda Function | מטרה | Routes | Auth |
|---|---|---|---|
| `pirkei-avot-search` | endpoints חיפוש ציבוריים | 5 GET routes | None |
| `pirkei-avot-semantic-search` | Bedrock KB + Nova Pro reranking | Direct invoke (ללא HTTP) | Internal |
| `pirkei-avot-admin` | ניהול תוכן + ניהול משתמשים | 13 routes | Cognito JWT |
| `pirkei-avot-settings` | הגדרות האתר | 2 routes | GET: None, PUT: JWT |
| `pirkei-avot-auth` | התחברות, הרשמה, איפוס סיסמה | 5 POST routes | None |
| `pirkei-avot-user` | מועדפים ופרופיל | 5 routes | Cognito JWT |

כל handler עוקב אחרי תבנית עקבית:

```python
def handler(event, context):
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    session = Session()
    try:
        if path == '/api/search/mishna' and method == 'GET':
            return _search_mishna(session, event)
        # ... more routes
        else:
            return error_response('הנתיב המבוקש לא נמצא', 'NOT_FOUND', 404)
    except SQLAlchemyError as e:
        logger.error(f'Database error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בגישה למסד הנתונים', 'INTERNAL_ERROR', 500)
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה פנימית', 'INTERNAL_ERROR', 500)
    finally:
        session.close()
```

עקרונות מרכזיים:
- **Session לכל invocation**: נוצר בתחילה, נסגר ב-`finally`
- **טיפול בשגיאות שכבתי**: שגיאות SQLAlchemy נתפסות בנפרד ל-rollback, catch-all כללי לכל השאר
- **הודעות שגיאה בעברית**: כל השגיאות שמוצגות למשתמש הן בעברית; קודים קריאים למכונה (`VALIDATION_ERROR`, `NOT_FOUND` וכו') לטיפול תכנותי
- **פונקציות פנימיות עם קידומת `_`**: ה-route handlers הם פרטיים, רק `handler()` הוא נקודת הכניסה

### שלב 3: צינור החיפוש הסמנטי

החלק המעניין ביותר בארכיטקטורה הוא החיפוש הסמנטי. כשמשתמש מקליד שאילתה בעברית כמו "מה אומרים על חכמה", המערכת צריכה למצוא משניות רלוונטיות לפי *משמעות*, לא רק התאמת מילות מפתח.

![Semantic Search Pipeline](semantic-search-pipeline.png)

הצינור עובד בשני שלבים:

**שלב 1 — Vector Search (Bedrock Knowledge Base):**
ה-Bedrock Knowledge Base מכיל את כל 108 המשניות מאונדקסות כ-vector embeddings. השאילתה מומרת לווקטור ו-20 השכנים הקרובים ביותר מאוחזרים.

**שלב 2 — LLM Reranking (Amazon Nova Pro):**
חיפוש וקטורי הוא טוב אבל רועש. 20 המועמדים נשלחים ל-Amazon Nova Pro (דרך ה-Converse API) עם prompt שמבקש לסנן תוצאות רלוונטיות באמת. ה-LLM מבין הקשר בעברית ומחזיר רק את המשניות שבאמת קשורות לשאילתה.

ה-search handler מפעיל את ה-semantic search Lambda ישירות דרך `boto3.client('lambda').invoke()` — ללא HTTP API Gateway באמצע. זה מהיר יותר (ללא HTTP overhead) ופשוט יותר (ללא API נוסף לנהל).

```python
# In search_handler.py
response = lambda_client.invoke(
    FunctionName=os.environ['SEMANTIC_SEARCH_FUNCTION_NAME'],
    InvocationType='RequestResponse',
    Payload=json.dumps({'query': query})
)
result = json.loads(response['Payload'].read())
# result = {'results': {'mishna_42': 0.95, 'mishna_7': 0.87, ...}}
```

ה-search handler אז מביא את רשומות המשנה בפועל מ-PostgreSQL, ממוינות לפי ציוני הרלוונטיות מה-LLM.

### שלב 4: המרת ה-Frontend (Jinja2 → Alpine.js)

כל Jinja2 template הומר לקובץ HTML סטטי עם Alpine.js components. דפוס ההמרה היה עקבי:

**לפני (Jinja2):**
```html
{% for result in results %}
  <div class="result-card">
    <h3>פרק {{ result.chapter }} • משנה {{ result.mishna }}</h3>
    <p>{{ result.text_pretty }}</p>
  </div>
{% endfor %}
```

**אחרי (Alpine.js):**
```html
<template x-for="result in results" :key="result.id">
  <div class="result-card">
    <h3 x-text="'פרק ' + result.chapter + ' • משנה ' + result.mishna"></h3>
    <p x-text="result.text_pretty"></p>
  </div>
</template>
```

ה-Alpine.js components העיקריים:

- **`searchApp()`** — מצב חיפוש ראשי, שלושה מצבי חיפוש, הצגת תוצאות, מועדפים
- **`tagSelection()`** — סינון תגיות, קיבוץ לפי קטגוריות, הצג עוד/פחות
- **`pirushModal()`** — צפייה ב-PDF עם Google Docs iframe, מצבי טעינה/ניסיון חוזר
- **`adminApp()`** — פאנל ניהול עם ניווט בטאבים, טפסי CRUD, ניהול משתמשים

תקשורת ה-API משתמשת בתבנית fetch פשוטה:

```javascript
async function apiGet(path) {
    const response = await fetch('/api' + path);
    if (response.status === 401) {
        localStorage.removeItem('authToken');
        window.location.href = '/login.html';
        return;
    }
    return response.json();
}
```

### שלב 5: מיגרציית אימות (Supabase Auth → Cognito)

ה-monolith השתמש ב-Supabase Auth להתחברות מנהלים. הגרסה ה-serverless משתמשת ב-Amazon Cognito עם User Pool שמוגדר לאימות email/password.

![Authentication Flow](auth-flow.png)

**זרימת האימות:**
1. המשתמש שולח credentials ב-`login.html`
2. ה-Frontend קורא ל-`POST /api/auth/login`
3. ה-Auth Lambda קורא ל-Cognito `InitiateAuth` (USER_PASSWORD_AUTH flow)
4. בהצלחה, מחזיר JWT ID token עם `custom:role` claim
5. ה-Frontend שומר את ה-token ב-`localStorage`
6. כל קריאות ה-API המוגנות כוללות `Authorization: Bearer <token>`
7. ה-API Gateway Cognito authorizer מאמת את ה-JWT לפני שה-Lambda מופעל

**גישה מבוססת תפקידים:**
- `custom:role = 'user'` → גישה לאזור האישי (מועדפים, פרופיל)
- `custom:role = 'admin'` → גישה לפאנל ניהול + ניהול משתמשים

ה-Cognito authorizer רץ ברמת ה-API Gateway, כך ש-tokens לא תקינים לעולם לא מגיעים ל-Lambda. זה גם מאובטח יותר וגם יעיל יותר מאימות tokens בקוד האפליקציה.

### שלב 6: Infrastructure as Code (AWS SAM)

כל התשתית מוגדרת בקובץ `template.yaml` יחיד באמצעות AWS SAM. זה כולל:

- 6 פונקציות Lambda עם event mappings
- 1 shared Lambda layer
- API Gateway HTTP API עם Cognito authorizer ו-rate limiting
- Cognito User Pool ו-Client
- S3 bucket לאחסון סטטי
- CloudFront distribution עם שני origins (S3 + API Gateway)
- CloudFront Origin Access Identity ל-S3
- IAM policies לכל פונקציית Lambda

ה-deployment אוטומטי עם סקריפט יחיד:

```bash
#!/usr/bin/env bash
set -euo pipefail

sam validate --lint          # אימות template
sam build --use-container    # בנייה ב-Docker (Python 3.12)
sam deploy                   # Deploy CloudFormation stack
aws s3 sync frontend/ ...   # סנכרון קבצים סטטיים ל-S3
aws cloudfront create-invalidation ...  # ניקוי CDN cache
```

הדגל `--use-container` חשוב — הוא בונה את חבילות ה-Lambda בתוך Docker container שתואם ל-Lambda runtime (Python 3.12), מה שמבטיח ש-dependencies מקומיים כמו `psycopg2` מקומפלים לפלטפורמה הנכונה.

---

## CloudFront: נקודת הכניסה המאוחדת

CloudFront משמש כנקודת כניסה יחידה גם ל-frontend הסטטי וגם ל-API. זה מושג באמצעות routing מבוסס נתיבים:

- **Default behavior** → S3 origin (HTML, CSS, JS, תמונות סטטיים)
- **`/api/*` behavior** → API Gateway origin (פונקציות Lambda)

מנקודת המבט של המשתמש, הכל מוגש מ-`https://pirkei-avot.online`. אין דומיין API נפרד, אין בעיות CORS בין frontend ל-backend (אותו origin), ו-CloudFront מטפל ב-HTTPS termination עם תעודת ACM.

נכסים סטטיים מקבלים את ה-caching ברירת המחדל של CloudFront. תגובות API מוגדרות עם מדיניות ללא caching כך שכל בקשה מגיעה ל-Lambda.

---

## אסטרטגיית חיבור לבסיס הנתונים

האופי הזמני של Lambda יוצר אתגר ייחודי לחיבורי בסיס נתונים. כל Lambda container יוצר חיבור משלו, ועם invocations מקבילים, אפשר למצות במהירות את מגבלת החיבורים של בסיס הנתונים.

הפתרון מורכב משני חלקים:

**1. צד ה-Lambda: הגדרות pool מינימליות**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=1,       # חיבור אחד לכל container
    max_overflow=0,    # לעולם לא ליצור נוספים
    pool_pre_ping=True # לאמת לפני שימוש
)
```

**2. צד בסיס הנתונים: Supabase pgbouncer pooler (port 6543)**

Supabase מספקת pgbouncer connection pooler מובנה. במקום להתחבר ישירות ל-PostgreSQL על port 5432, Lambda מתחבר ל-pooler על port 6543. ה-pooler מרבב חיבורי לקוחות רבים על מספר קטן יותר של חיבורים בפועל לבסיס הנתונים באמצעות transaction-mode pooling.

זה אומר ש-100 Lambda containers מקבילים (100 חיבורי לקוח) עשויים לחלוק רק 10 חיבורי PostgreSQL בפועל. מחרוזת החיבור זהה למעט מספר ה-port.

---

## מה השתנה ומה לא

### השתנה
- **Runtime**: Flask/Gunicorn → AWS Lambda (Python 3.12)
- **Hosting**: Render → S3 + CloudFront
- **Templates**: Jinja2 → Alpine.js + static HTML
- **Auth**: Supabase Auth → Amazon Cognito
- **ORM**: Flask-SQLAlchemy → plain SQLAlchemy `declarative_base()`
- **Deployment**: Git push ל-Render → `sam deploy` + S3 sync
- **הפעלת חיפוש סמנטי**: קריאת HTTP API → Lambda-to-Lambda invoke

### לא השתנה
- **Database**: אותו instance של Supabase PostgreSQL, אותו schema, אותם נתונים
- **מודלי בסיס נתונים**: אותן טבלאות (Mishna, Tag, Category, SiteSetting, mishna_tag)
- **UI/UX**: אותו layout עברי RTL, ערכת נושא זהב/כהה, אפקטי glassmorphism, אנימציות
- **התנהגות חיפוש**: אותו חיפוש רב-מודאלי (פרק/משנה, חכם, תגיות, ניווט לפי מספר)
- **צינור חיפוש סמנטי**: אותו Bedrock KB + Nova Pro reranking logic


---

## לקחים שנלמדו

### 1. אתחול ברמת המודול חשוב

ב-Lambda, כל דבר שמאותחל מחוץ לפונקציית ה-handler נשמר בין invocations חמים. ה-database engine, לקוחות boto3 וקריאות הגדרות צריכים כולם לקרות ברמת המודול. זה הפך עונש cold start של ~500ms ל-warm invocation של ~50ms.

### 2. Connection pooling הוא הכרחי

ללא ה-pgbouncer pooler של Supabase, האפליקציה הייתה מגיעה למגבלת חיבורים תוך דקות תחת עומס בינוני. כל Lambda container מחזיק חיבור אחד, ו-containers יכולים להתרחב למאות. ה-pooler הוא שסתום הביטחון.

### 3. Lambda-to-Lambda invoke עדיף על HTTP לקריאות פנימיות

ה-semantic search Lambda לעולם לא נקרא ישירות על ידי משתמשים — רק על ידי ה-search handler. שימוש ב-`boto3.client('lambda').invoke()` במקום HTTP API Gateway endpoint מבטל HTTP overhead, מפשט IAM (ללא ניהול API key), ומפחית latency.

### 4. Alpine.js לא מוערך מספיק למקרה הזה

לאפליקציה ממוקדת תוכן עם אינטראקטיביות מתונה, Alpine.js פוגע בנקודה המתוקה. ללא build step, ה-frontend הוא באמת סטטי — רק קבצי HTML ב-S3 bucket. כל ה-frontend עולה תוך שניות עם `aws s3 sync`.

### 5. SAM הופך תשתית לניתנת לניהול

כל משאבי ה-AWS בקובץ `template.yaml` יחיד אומר שהתשתית נמצאת ב-version control, ניתנת לסקירה ולשחזור. `sam deploy` הוא אינקרמנטלי — הוא מעדכן רק משאבים שהשתנו. שינוי קוד Lambda עולה תוך פחות מדקה.

### 6. deployment דו-שלבי מפחית סיכון

deploy קודם ל-CloudFront URL (שלב 1) וחיבור הדומיין המותאם רק אחרי אימות (שלב 2) אומר שה-deployment הקיים על Render נשאר חי עד שה-stack החדש נבדק במלואו. מיגרציה ללא זמן השבתה.

---

## השוואת עלויות

| רכיב | Render (לפני) | AWS Serverless (אחרי) |
|---|---|---|
| Compute | Free tier (עם cold starts) או $7/חודש | Lambda: ~$0.50/חודש (תשלום לפי בקשה) |
| Database | Supabase free tier | Supabase free tier (ללא שינוי) |
| CDN | אין | CloudFront: ~$1/חודש |
| Auth | Supabase Auth (חינם) | Cognito: free tier (50K MAU) |
| SSL | מנוהל על ידי Render | ACM (חינם) |
| AI Search | Lambda + Bedrock (~$2/חודש) | זהה (~$2/חודש) |
| **סה"כ** | **$0–$7/חודש** | **~$3.50/חודש** |

הגרסה ה-serverless עולה בערך כמו ה-tier בתשלום של Render, אבל ללא cold starts, עם סקלביליות עצמאית, ועם CDN מול הכל.

---

## מבנה הפרויקט (סופי)

```
├── template.yaml              # תשתית SAM (כל משאבי AWS)
├── samconfig.toml             # הגדרות deployment (gitignored)
├── scripts/deploy.sh          # צינור deployment אוטומטי
├── functions/
│   ├── search/                # חיפוש ציבורי (5 endpoints)
│   ├── semantic_search/       # Bedrock KB + Nova Pro reranking
│   ├── admin/                 # Admin CRUD + ניהול משתמשים
│   ├── settings/              # הגדרות אתר (pirush toggle)
│   ├── auth/                  # התחברות, הרשמה, איפוס סיסמה
│   └── user/                  # מועדפים, פרופיל
├── layers/shared/             # Shared Lambda layer
│   ├── models.py              # SQLAlchemy models
│   ├── db.py                  # Database engine + session factory
│   ├── response.py            # API response helpers
│   ├── text_utils.py          # נרמול טקסט עברי
│   ├── constants.py           # מיפויי פרק/משנה
│   └── requirements.txt       # Layer dependencies
├── frontend/                  # אתר סטטי (S3 + CloudFront)
│   ├── index.html             # דף חיפוש ראשי (Alpine.js)
│   ├── manage.html            # פאנל ניהול
│   ├── login.html             # דף התחברות
│   ├── register.html          # דף הרשמה
│   ├── personal.html          # אזור אישי (מועדפים)
│   ├── error.html             # דף שגיאה
│   └── static/                # CSS, תמונות, אנימציות Lottie
├── tests/                     # Unit tests (pytest)
└── docs/                      # מדריך deployment, מדריך פיתוח
```

---

## סיכום

מיגרציה מ-Flask monolith ל-AWS serverless לא הייתה רק שינוי של איפה הקוד רץ. זה היה שינוי מהותי באופן שבו האפליקציה בנויה:

- **פירוק**: monolith אחד הפך לשש פונקציות Lambda ממוקדות עם גבולות ברורים
- **Frontend סטטי**: templates שרונדרו בשרת הפכו לקבצים סטטיים עם CDN caching
- **אימות מנוהל**: קוד אימות מותאם הפך לשירות Cognito מנוהל
- **Infrastructure as code**: הגדרה ידנית ב-Render הפכה ל-SAM template ב-version control
- **אינטגרציית AI**: צינור החיפוש הסמנטי, שכבר היה על AWS, הפך לאזרח מהשורה הראשונה במקום קריאת API חיצונית

התוצאה היא אפליקציה שמתכווצת לאפס כשהיא לא פעילה, מטפלת בפיקים של תעבורה ללא התערבות, עולה תוך פחות משתי דקות, ועולה כמה דולרים בחודש להפעלה.

בסיס הנתונים לא זז. ה-UI לא השתנה. המשתמשים לא שמו לב. זו המיגרציה הטובה ביותר.

---

*נבנה על ידי [מוטי שאול](https://www.linkedin.com/in/moti-shaul). הפרויקט חי ב-[pirkei-avot.online](https://pirkei-avot.online).*