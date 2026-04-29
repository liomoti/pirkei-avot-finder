# Project Structure

## Root Level

- `template.yaml`: AWS SAM infrastructure template (all AWS resources)
- `samconfig.toml`: SAM deployment configuration (gitignored — contains secrets)
- `README.md`: Project documentation

## Directory Organization

### `/functions`
Lambda function handlers (one directory per function):

- `search/search_handler.py`: Public search endpoints — chapter/mishna, smart search, tag search, navigate by number, get all tags
- `semantic_search/semantic_search_handler.py`: Bedrock Knowledge Base vector search + Nova Pro LLM reranking (invoked directly by search handler, not via HTTP)
- `admin/admin_handler.py`: Authenticated admin CRUD — mishna create/update, tag CRUD, category creation, get all tags
- `settings/settings_handler.py`: Site settings — get pirush_enabled, toggle pirush
- `auth/auth_handler.py`: Cognito authentication — login (USER_PASSWORD_AUTH), logout

### `/layers/shared`
Shared Lambda layer (deployed to all functions except semantic_search):

- `models.py`: SQLAlchemy models (Mishna, Tag, Category, SiteSetting, mishna_tag) with plain declarative base
- `db.py`: Database engine and session factory (module-level initialization for warm invocation reuse)
- `text_utils.py`: Hebrew text normalization (niqqud removal, U+0591–U+05C7)
- `constants.py`: ALLOWED_CHAPTERS mapping (6 chapters, Hebrew letter keys)
- `response.py`: API Gateway response helpers (success_response, error_response, serialize_mishna)
- `requirements.txt`: Layer pip dependencies (sqlalchemy, psycopg2-binary)

### `/frontend`
Static site served from S3 via CloudFront:

- `index.html`: Main search page (Alpine.js searchApp, tagSelection, pirushModal components)
- `manage.html`: Admin panel (Alpine.js adminApp — mishna/tag/category CRUD, pirush toggle)
- `login.html`: Admin login page (Cognito authentication)
- `error.html`: Error display page
- `static/style.css`: Custom CSS (gold/dark theme, glassmorphism, animations)
- `static/pics/`: Images, logos, Lottie JSON animations

### `/scripts`
- `deploy.sh`: Automated deployment (sam build → sam deploy → S3 sync → CloudFront invalidation)

### `/tests`
- `test_response.py`: Unit tests for response helpers and Mishna serialization
- `test_aws_search_client.py`: Unit tests for AWS search client (monolith-era, still valid)

### `/docs`
- `DEPLOYMENT_GUIDE.md`: Full deployment walkthrough (Phase 1: deploy, Phase 2: custom domain)

### `/monolith`
Archived Flask/Gunicorn monolith code (preserved for reference, not deployed):
- `app.py`, `routes.py`, `models.py`, `forms.py`, `config.py`, etc.
- `templates/`: Jinja2 templates (ported to Alpine.js in `/frontend`)
- `scripts/`: Old utility scripts (create_db, check_memory, etc.)

## Architecture Patterns

### Lambda Handler Pattern
Each handler follows: parse event → create session → route dispatch → business logic → close session. Outer try/except catches SQLAlchemy and general errors. Session created per invocation, closed in finally block.

### Shared Layer
Common modules packaged as a Lambda layer. SAM builds with `BuildMethod: python3.12` to install pip dependencies alongside custom modules. All functions except semantic_search use this layer.

### Lambda-to-Lambda Invoke
Search handler invokes semantic search Lambda directly via `boto3.client('lambda').invoke()` — no HTTP API Gateway in between. Faster and simpler than HTTP-based approach.

### Database Models
- `Mishna`: Composite ID (`chapter_mishna`), unique sequential number (1-108), dual text fields (pretty/raw)
- `Tag`: Hierarchical with category relationship, unique name
- `Category`: Color-coded tag categories (default #F5F5F5)
- `SiteSetting`: Key-value store for site configuration (pirush_enabled)
- `mishna_tag`: Many-to-many association table

### Frontend Components (Alpine.js)
- `searchApp()`: Main search state, three search modes, result rendering
- `tagSelection()`: Tag filtering, category grouping, show-more toggles
- `pirushModal()`: PDF viewer with Google Docs iframe, loading/retry states
- `adminApp()`: Admin panel with tabbed navigation, CRUD forms, auth management

### Error Handling
- Lambda: outer try/except with Hebrew error messages, SQLAlchemy rollback on DB errors
- Frontend: fetch errors display Hebrew messages, 401 triggers redirect to login
- API Gateway: Cognito authorizer returns 401 for invalid/missing JWT, rate limiter returns 429

## Code Conventions

- Hebrew text normalization: Use `remove_niqqud()` for search operations
- Logging: Use Python `logging` module (`logger = logging.getLogger()`)
- Database operations: Always wrap in try/except with session.rollback() on SQLAlchemyError
- Rate limiting: API Gateway route-level throttling (20 req/min burst on search endpoints)
- Authentication: API Gateway Cognito JWT authorizer on admin routes
- Response format: `success_response(body)` and `error_response(message, code, status)`
