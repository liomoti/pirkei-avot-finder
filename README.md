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
                                                   → Bedrock Knowledge Base
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Alpine.js, Tailwind CSS, Lottie.js — static HTML served from S3 |
| CDN | CloudFront with custom domain and ACM certificate |
| API | API Gateway HTTP API with Cognito JWT authorizer |
| Compute | AWS Lambda (Python 3.12) — 5 functions |
| Database | PostgreSQL on Supabase (via pgbouncer pooler, port 6543) |
| Auth | Amazon Cognito User Pool (email/password) |
| AI Search | Bedrock Knowledge Base + Amazon Nova Pro (LLM reranking) |
| IaC | AWS SAM (template.yaml) |

### Lambda Functions

| Function | Routes | Auth |
|---|---|---|
| `pirkei-avot-search` | `GET /api/search/mishna`, `/smart`, `/tags`, `/tags/all`, `/number/{n}` | Public |
| `pirkei-avot-semantic-search` | Invoked directly by search handler (no HTTP route) | Internal |
| `pirkei-avot-admin` | `GET/POST /api/admin/mishna`, `GET/POST/PUT/DELETE /api/admin/tag*`, `POST /api/admin/category` | Cognito JWT |
| `pirkei-avot-settings` | `GET /api/settings`, `PUT /api/settings/pirush` | GET: Public, PUT: JWT |
| `pirkei-avot-auth` | `POST /api/auth/login`, `POST /api/auth/logout` | Public |

### Semantic Search

The semantic search uses a two-stage pipeline:

1. **Vector retrieval** — Bedrock Knowledge Base returns top 20 candidates from indexed Pirkei Avot documents
2. **LLM reranking** — Amazon Nova Pro (via Converse API) filters candidates by relevance to the Hebrew query

The search handler invokes the semantic search Lambda directly (Lambda-to-Lambda via boto3) — no HTTP API Gateway in between.

### Database Schema

- **Mishna**: Composite ID (`chapter_mishna`), unique sequential number (1-108), dual text fields (`text_pretty` with niqqud, `text_raw` normalized)
- **Tag**: Hierarchical with category relationship, unique name
- **Category**: Color-coded tag categories (default `#F5F5F5`)
- **SiteSetting**: Key-value store (`pirush_enabled`)
- **mishna_tag**: Many-to-many association table

The database is hosted on Supabase PostgreSQL. Lambda connects via the pgbouncer connection pooler (port 6543) with `pool_size=1, max_overflow=0` per container.

### Project Structure

```
├── template.yaml              # SAM infrastructure (all AWS resources)
├── samconfig.toml             # Deployment config (gitignored)
├── scripts/deploy.sh          # Build + deploy + S3 sync + cache invalidation
├── functions/
│   ├── search/                # Search handler (5 public endpoints)
│   ├── semantic_search/       # Bedrock KB + Nova Pro reranking
│   ├── admin/                 # Admin CRUD (Cognito-protected)
│   ├── settings/              # Site settings
│   └── auth/                  # Cognito login/logout
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
├── tests/                     # Unit tests
├── docs/
│   └── DEPLOYMENT_GUIDE.md    # Full deployment walkthrough
└── monolith/                  # Archived Flask/Gunicorn code (reference only)
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
- No self-registration — admin users created via AWS CLI only

### Region

All services in `us-east-2` (Ohio), except ACM certificate in `us-east-1` (CloudFront requirement).

### Future Roadmap

- User accounts with Cognito self-registration and personal area
- Saved searches and bookmarks
- Export search results to PDF
- Analytics dashboard for content insights
- Multi-language support (English translation)
