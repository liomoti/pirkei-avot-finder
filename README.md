# Pirkei Avot Finder - חיפוש חכם בפרקי אבות

## תקציר הפרויקט (למשתמשים)

**Pirkei Avot Finder** היא אפליקציית אינטרנט חכמה לחיפוש ולמידה של משניות מספר פרקי אבות. האתר מאפשר למשתמשים למצוא משניות בקלות באמצעות מספר דרכי חיפוש:

### יכולות החיפוש:
- **חיפוש לפי פרק ומשנה** - מציאת משנה ספציפית לפי מספרה
- **חיפוש חכם** - חיפוש טקסט חופשי עם שני מצבים:
  - **התאמה מדויקת** - מוצא את הטקסט המדויק בתוך המשניות
  - **חיפוש סמנטי** - מוצא משניות לפי משמעות התוכן (בעזרת בינה מלאכותית)
- **חיפוש לפי נושאים** - מציאת כל המשניות הקשורות לנושא מסוים (כמו: חכמה, תורה)
- **ניווט לפי מספר משנה** - קפיצה ישירה למשנה מסוימת

### תכונות נוספות:
- ממשק משתמש מעוצב ואסתטי בעברית
- תיוג משניות לפי קטגוריות נושאיות
- מערכת ניהול תוכן למנהלים (הוספה ועריכה של משניות)
- צפייה בפירוש למשניות (Google Docs Viewer)
- חוויית משתמש מהירה ונוחה

האתר מיועד לסטודנטים, מורים, חוקרים וכל אדם המעוניין ללמוד ולחפש במסכת פרקי אבות בצורה יעילה ומתקדמת.

🔗 **[pirkei-avot.online](https://pirkei-avot.online)**

---

## Technical Overview (For Developers)

### Architecture

Pirkei Avot Finder is a fully serverless application running on AWS, built with AWS SAM (Serverless Application Model).

```
User → CloudFront → S3 (static frontend)
                  → API Gateway → Lambda functions → Supabase PostgreSQL
                                                   → Bedrock (Knowledge Base retrieval and/or Nova Pro)
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Alpine.js, Tailwind CSS, Lottie.js — static HTML served from S3 |
| CDN | CloudFront with custom domain and ACM certificate |
| API | API Gateway HTTP API with Cognito JWT authorizer |
| Compute | AWS Lambda (Python 3.12) — 8 functions |
| Database | PostgreSQL on Supabase (via pgbouncer pooler, port 6543) |
| Auth | Amazon Cognito User Pool (email/password, self-registration for regular users) |
| AI Search | Two selectable pipelines — Bedrock Knowledge Base + Amazon Nova Pro reranking, or full-context Nova Pro (no retrieval) |
| IaC | AWS SAM (template.yaml) |

### Lambda Functions

| Function | Routes | Auth |
|---|---|---|
| `pirkei-avot-search` | `GET /api/search/mishna`, `/smart`, `/tags`, `/tags/all`, `/number/{n}` | Public |
| `pirkei-avot-semantic-search` | Invoked directly by search handler (no HTTP route) | Internal |
| `pirkei-avot-json-context-search` | Invoked directly by search handler (no HTTP route) | Internal |
| `pirkei-avot-admin` | `GET/POST /api/admin/mishna`, tag/category CRUD, `GET /api/admin/users*`, `GET /api/admin/search-logs*`, `POST /api/admin/generate-cache` | Cognito JWT (`custom:role=admin`) |
| `pirkei-avot-settings` | `GET /api/settings`, pirush + pirush-options CRUD, `PUT /api/settings/semantic-search-method` | GET: Public, writes: JWT |
| `pirkei-avot-auth` | `POST /api/auth/register`, `/login`, `/logout`, `/forgot-password`, `/confirm-reset` | Public |
| `pirkei-avot-cache-generator` | Invoked directly by admin function (no HTTP route) | Internal |
| `pirkei-avot-user` | `GET/POST /api/user/favorites`, `GET/POST /api/user/learned`, `GET /api/user/progress`, `GET/PUT /api/user/profile` | Cognito JWT |

### Semantic Search

Search supports two selectable AI pipelines, toggled via `PUT /api/settings/semantic-search-method`:

1. **Bedrock KB + reranking** (`pirkei-avot-semantic-search`) — Bedrock Knowledge Base vector retrieval returns the top 20 candidates, then Amazon Nova Pro (via Converse API) reranks them by relevance to the Hebrew query.
2. **Full-context, no retrieval** (`pirkei-avot-json-context-search`) — the entire cached mishnayot JSON (`static/mishnaiot.json`, built by `pirkei-avot-cache-generator`) is passed directly to Nova Pro as context, skipping Bedrock KB retrieval entirely.

The search handler invokes whichever Lambda is configured directly (Lambda-to-Lambda via boto3) — no HTTP API Gateway in between. AI search queries are logged to `AiSearchLog` and viewable by admins via `GET /api/admin/search-logs`.

### User Accounts & Personal Area

Regular users can self-register (`POST /api/auth/register`, assigned `custom:role=user`) separately from admin accounts (`custom:role=admin`, still provisioned manually). Authenticated users can:

- Favorite mishnayot (`/api/user/favorites`)
- Track learned mishnayot and view progress (`/api/user/learned`, `/api/user/progress`)
- View/update their profile (`/api/user/profile`)

### Database Schema

- **Mishna**: Composite ID (`chapter_mishna`), unique sequential number (1-108), dual text fields (`text_pretty` with niqqud, `text_raw` normalized)
- **Tag**: Hierarchical with category relationship, unique name
- **Category**: Color-coded tag categories (default `#F5F5F5`)
- **SiteSetting**: Key-value store (`pirush_enabled`, pirush options)
- **mishna_tag**: Many-to-many association table
- **UserFavorite**: Per-user favorited mishnayot
- **UserLearned**: Per-user learned-mishna tracking (powers progress view)
- **AiSearchLog**: Logged AI search queries, viewable via the admin search-logs endpoint

The database is hosted on Supabase PostgreSQL. Lambda connects via the pgbouncer connection pooler (port 6543) with `pool_size=1, max_overflow=0` per container.

### Project Structure

```
├── template.yaml              # SAM infrastructure (all AWS resources)
├── samconfig.toml             # Deployment config (gitignored)
├── scripts/deploy.sh          # Build + deploy + S3 sync + cache invalidation
├── functions/
│   ├── search/                # Search handler (public endpoints)
│   ├── semantic_search/       # Bedrock KB + Nova Pro reranking
│   ├── json_context_search/   # Full-context Nova Pro search (no Bedrock KB retrieval)
│   ├── admin/                 # Admin CRUD, user management, search-log viewer (Cognito-protected)
│   ├── settings/              # Site settings, pirush options, search-method toggle
│   ├── auth/                  # Cognito register/login/logout/password-reset
│   ├── cache_generator/       # Builds static/mishnaiot.json cache, invoked by admin function
│   └── user/                  # Favorites, learned tracking, profile (Cognito-protected)
├── layers/shared/             # Shared Lambda layer
│   ├── models.py              # SQLAlchemy models (plain declarative base)
│   ├── db.py                  # Engine + session factory
│   ├── response.py            # API Gateway response helpers
│   ├── text_utils.py          # Niqqud removal
│   ├── constants.py           # ALLOWED_CHAPTERS mapping
│   └── requirements.txt       # Layer dependencies (sqlalchemy, psycopg2-binary)
├── frontend/                  # Static site (S3 + CloudFront)
│   ├── index.html             # Main search page
│   ├── manage.html            # Admin panel
│   ├── login.html             # Admin login
│   ├── error.html             # Error page
│   └── static/                # CSS, images, Lottie animations
├── tests/                     # Unit tests (unittest + hypothesis property-based tests)
└── docs/
    ├── DEPLOYMENT_GUIDE.md    # Full deployment walkthrough
    └── DAILY_DEV_GUIDE.md     # Day-to-day dev workflows
```

### Deployment

The application deploys to AWS using SAM CLI. See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for the full walkthrough.

Quick deploy:

```bash
./scripts/deploy.sh
```

This runs `sam build --use-container` → `sam deploy` → S3 sync → CloudFront invalidation.

**Prerequisites**: AWS CLI, SAM CLI, Docker. Python 3.12 is not required locally — Docker handles the build environment.

### Configuration

All configuration is in `samconfig.toml` (gitignored). Key parameters:

| Parameter | Description |
|---|---|
| `DatabaseUrl` | Supabase PostgreSQL pooler URL (port 6543) |
| `KnowledgeBaseId` | Bedrock Knowledge Base ID (default: `HAFIDLHKGC`) |
| `DomainName` | Custom domain (default: `pirkei-avot.online`) |
| `AcmCertificateArn` | ACM certificate for HTTPS (us-east-1) |

### Security

- Cognito JWT authorizer on all admin API routes
- API Gateway rate limiting (20 req/min on search endpoints)
- Database credentials passed as SAM parameters with `NoEcho: true`
- `samconfig.toml` gitignored (contains secrets)
- SSL/TLS for database connections (`sslmode=require`)
- Self-registration (`/api/auth/register`) creates regular `custom:role=user` accounts only; admin accounts (`custom:role=admin`) are still provisioned manually via AWS CLI

### Region

All services in `us-east-2` (Ohio), except ACM certificate in `us-east-1` (CloudFront requirement).

### Future Roadmap

- Saved searches
- Export search results to PDF
- Analytics dashboard for content insights (beyond the current admin AI search-log viewer)
- Multi-language support (English translation)
