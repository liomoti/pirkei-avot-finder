# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

Pirkei Avot Finder is a Hebrew-language web app for searching and studying Mishnayot from Pirkei Avot (Ethics of the Fathers). It's a fully serverless AWS application: static frontend on S3/CloudFront, Python 3.12 Lambda functions behind API Gateway, PostgreSQL on Supabase, Cognito auth, and Bedrock (Nova Pro) for AI-assisted search. Infrastructure is defined entirely in `template.yaml` (AWS SAM) — treat it as the source of truth for routes/functions, since some of the prose docs below have drifted out of date.

## Commands

**Tests**
```bash
pytest tests/                      # all tests
pytest tests/test_response.py -v   # single file
```

**Deploy**
```bash
sam validate --lint          # validate template.yaml after changes
./scripts/deploy.sh          # full pipeline: build → deploy → S3 sync → CloudFront invalidation
sam build --use-container    # build only (Docker required, builds Python 3.12 env)
sam deploy                   # deploy only (backend-only, skips frontend sync)
```
Python 3.12 is not required locally — Docker handles the Lambda build environment.

**Frontend-only changes** (no Lambda rebuild needed):
```bash
aws s3 sync frontend/ "s3://pirkei-avot.online-frontend" --region us-east-2 --delete && aws cloudfront create-invalidation --distribution-id E5J34MEGJDS08 --paths "/*"
```

**Local frontend dev**
```bash
cd frontend && python3 -m http.server 8080   # API calls hit prod CloudFront URL (hardcoded in HTML)
sam local start-api --port 3000              # full local stack; needs Docker + reachable DB; semantic search needs Bedrock access
```

**Logs**
```bash
sam logs --name SearchFunction --stack-name pirkei-avot-serverless --tail
```

## Architecture

```
User → CloudFront → S3 (static frontend)
                  → API Gateway → Lambda functions → Supabase PostgreSQL (pgbouncer :6543)
                                                    → Bedrock (Nova Pro)
```

### Lambda functions

All defined in `template.yaml`; verify there before trusting older docs, which are missing three of these.

| Function (`FunctionName`) | CodeUri | Routes | Auth |
|---|---|---|---|
| `pirkei-avot-search` | `functions/search/` | `GET /api/search/{mishna,smart,tags,tags/all,number/{n}}` | Public |
| `pirkei-avot-semantic-search` | `functions/semantic_search/` | Lambda-to-Lambda only (invoked by search handler) | Internal |
| `pirkei-avot-json-context-search` | `functions/json_context_search/` | Lambda-to-Lambda only (invoked by search handler) | Internal |
| `pirkei-avot-admin` | `functions/admin/` | `POST /api/admin/mishna`, tag/category CRUD, `GET /api/admin/users*`, `GET /api/admin/search-logs`, `POST /api/admin/generate-cache` | Cognito JWT |
| `pirkei-avot-settings` | `functions/settings/` | `GET /api/settings`, pirush options CRUD, `PUT /api/settings/semantic-search-method` | GET public, writes JWT |
| `pirkei-avot-auth` | `functions/auth/` | `POST /api/auth/{register,login,logout,forgot-password,confirm-reset}` | Public |
| `pirkei-avot-cache-generator` | `functions/cache_generator/` | Invoked synchronously by admin function (`generate-cache`) | Internal |
| `pirkei-avot-user` | `functions/user/` | `GET/POST /api/user/favorites`, `GET/POST /api/user/learned`, `GET /api/user/progress`, `GET/PUT /api/user/profile` | Cognito JWT |

### Two semantic search implementations (mid-migration)

There are currently two competing implementations for AI-assisted search, chosen at runtime via the `semantic-search-method` setting (`PUT /api/settings/semantic-search-method`):

- **`semantic_search`** (older) — Bedrock Knowledge Base vector retrieval (top 20 candidates) followed by Nova Pro LLM reranking.
- **`json_context_search`** (newer, "no-RAG") — passes the entire cached mishnayot JSON (`static/mishnaiot.json`, built by the cache-generator function) directly to Nova Pro via the Converse API as context, skipping Bedrock KB retrieval entirely.

The search handler (`functions/search/search_handler.py`) reads the configured method and Lambda-invokes the corresponding function directly via `boto3.client('lambda').invoke()` — no HTTP hop.

### Lambda handler pattern

Every handler follows the same shape: parse `rawPath` + HTTP method from the event → dispatch to an internal `_`-prefixed route function → business logic → return via `success_response`/`error_response` helpers. A `Session()` is created per invocation and closed in a `finally` block. Outer `try/except` separately catches `SQLAlchemyError` (rollback + Hebrew DB-error message) and generic `Exception` (Hebrew generic-error message) — errors are never allowed to propagate unhandled.

### Shared layer (`layers/shared/`)

Packaged as a Lambda layer, used by every function except `semantic_search` and `json_context_search` (which only need `boto3`):
- `models.py` — SQLAlchemy models with a plain declarative base (no Flask-SQLAlchemy): `Mishna`, `Tag`, `Category`, `SiteSetting`, `mishna_tag` (association table), plus `UserFavorite`/`UserLearned` for the personal-area feature.
- `db.py` — engine + session factory, initialized at module level for warm-invocation reuse (`pool_size=1, max_overflow=0, pool_pre_ping=True, pool_recycle=300`) against the Supabase pgbouncer pooler.
- `response.py` — `success_response(body)`, `error_response(message, code, status)`, plus serializers (`serialize_mishna`, `serialize_favorite`).
- `text_utils.py` — `remove_niqqud()` for Hebrew text normalization (strips U+0591–U+05C7) before search matching.
- `constants.py` — `ALLOWED_CHAPTERS` mapping.

### Auth flow

Cognito User Pool, `USER_PASSWORD_AUTH` flow. Frontend stores the IdToken from login in `localStorage` and sends `Authorization: Bearer <token>` on protected calls; API Gateway's Cognito authorizer validates the JWT before the Lambda runs. A 401 in the frontend triggers redirect to `login.html`.

## Code conventions

- User-facing strings (errors, UI text) are in Hebrew; code and comments are in English.
- `snake_case` for functions/variables; internal route-dispatch functions are prefixed `_` (e.g. `_search_mishna`).
- Database writes are always wrapped in `try/except SQLAlchemyError` with `session.rollback()`.
- Logging via stdlib `logging` (`logger = logging.getLogger()`), not print statements; errors logged with `exc_info=True`.
- No type hints on most functions; single-quoted strings; f-strings for interpolation.

## Testing conventions

- `unittest.TestCase` + `unittest.mock`, with `setUp` fixtures and Arrange/Act/Assert comments.
- Some test files (`tests/test_pbt_*.py`) use `hypothesis` for property-based testing — these generate and cache examples under `.hypothesis/`.
- `conftest.py` makes the SAM-built shared layer importable as `layers.shared.python.*` by pointing at `.aws-sam/build/SharedLayer` — run `sam build` at least once before running tests if imports fail.

## Further reading

`docs/DAILY_DEV_GUIDE.md` and `docs/DEPLOYMENT_GUIDE.md` cover day-to-day workflows and full deployment steps in more detail. `.kiro/steering/*.md` and `README.md` contain additional design/product context, but their Lambda function inventories are stale (missing `json_context_search`, `cache_generator`, and `user`) — cross-check against `template.yaml` rather than trusting them for the current function/route list.
