# Design Guide

This document defines the coding standards, style conventions, and design patterns for the Pirkei Avot Finder project. It serves as the single source of truth for how code should be written and organized.

## Goals

- Consistency across all Lambda handlers, shared modules, and frontend code
- Readability for Hebrew-first application with English code comments
- Maintainability through clear patterns and conventions
- Reliability through structured error handling and logging

## Language and Formatting

### Python

**Formatting**
- No type hints on most functions
- Single quotes for strings, f-strings for interpolation
- 4-space indentation (PEP 8)
- Blank line between logical sections within functions
- Maximum line length: follow PEP 8 guidelines (79 chars soft, 120 hard)

**Naming**
- `snake_case` for variables, functions, modules
- `PascalCase` for classes and exceptions
- `UPPER_SNAKE_CASE` for constants and config values
- Private/internal functions prefixed with `_` (e.g., `_search_mishna`, `_parse_body`)

**Imports**
- Standard library first, then third-party, then local (shared layer) — separated by blank lines
- Direct imports from shared layer: `from db import Session`, `from models import Mishna`
- No `__all__` exports

**Documentation**
- Module-level docstrings with triple double-quotes on multi-line blocks
- Class docstrings describe attributes in Google-style format
- Inline comments in English
- User-facing strings (error messages, UI text) in Hebrew

### HTML / CSS

**HTML**
- Full HTML5 documents with `<!DOCTYPE html>`, `<html lang="he" dir="rtl">`
- Tailwind CSS via CDN for utility classes
- Alpine.js via CDN for reactive components
- No Jinja2 — all rendering is client-side

**CSS**
- Section comments with `/* ===== SECTION NAME ===== */`
- Properties grouped: positioning → display → box model → typography → visual → animation
- `!important` used to override Tailwind defaults where needed

### YAML (SAM Template)

- Section comments with `# ============================================================`
- Parameters: `PascalCase` (e.g., `DatabaseUrl`, `KnowledgeBaseId`)
- Resource names: `PascalCase` (e.g., `SearchFunction`, `SharedLayer`)
- Function names: kebab-case with `pirkei-avot-` prefix (e.g., `pirkei-avot-search`)
- Sensitive parameters: `NoEcho: true`

## Design Patterns

### Lambda Handler Pattern

Each Lambda function follows a consistent structure:

```python
def handler(event, context):
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    session = Session()
    try:
        # Route dispatch to internal _functions
        if path == '/api/...' and method == 'GET':
            return _handle_route(session, params)
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

Key principles:
- One `handler()` entry point per function
- Route dispatch based on `rawPath` and HTTP method
- Session created per invocation, closed in `finally`
- Internal route functions prefixed with `_`
- Outer try/except catches all unhandled errors

### API Response Format

All API responses use consistent helpers:

```python
# Success
success_response(body, status=200)
# → {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": "..."}

# Error
error_response(message, code, status)
# → {"statusCode": N, "body": "{\"error\": \"Hebrew message\", \"code\": \"MACHINE_CODE\"}"}
```

Error codes: `VALIDATION_ERROR`, `NOT_FOUND`, `DUPLICATE_ENTRY`, `AUTH_REQUIRED`, `RATE_LIMITED`, `SEARCH_FAILED`, `INTERNAL_ERROR`

### Database Access Pattern

- Engine and session factory initialized at module level (outside handler) for warm invocation reuse
- `pool_size=1, max_overflow=0` — one connection per Lambda container
- `pool_pre_ping=True` — verify connection before use
- `pool_recycle=300` — refresh connections every 5 minutes
- Database writes always wrapped in `try/except SQLAlchemyError` with `session.rollback()`

### Frontend Component Pattern (Alpine.js)

Page-level components defined as functions returning state objects:

```javascript
function searchApp() {
    return {
        // State
        results: [],
        loading: false,
        // Methods
        async performSearch() { ... },
        // Lifecycle
        init() { this.fetchSettings(); }
    };
}
```

API communication via helper functions:
- `apiGet(path)` — public endpoints
- `apiAuthGet(path)` — authenticated endpoints (includes JWT from localStorage)
- Auto-redirect to `/login.html` on 401 responses

### Authentication Flow

1. Admin submits email/password on `login.html`
2. Frontend calls `POST /api/auth/login`
3. Auth handler calls Cognito `InitiateAuth` (USER_PASSWORD_AUTH)
4. On success, returns IdToken to frontend
5. Frontend stores token in `localStorage`
6. All admin API calls include `Authorization: Bearer <token>`
7. API Gateway Cognito authorizer validates JWT on admin routes
8. Public routes use `Auth: { Authorizer: NONE }`

## Error Handling

### Lambda (Backend)

- Outer `try/except Exception` in every handler — never let unhandled errors propagate
- Inner `try/except SQLAlchemyError` for database writes with `session.rollback()`
- All error responses use Hebrew user-facing messages
- Log errors with `exc_info=True` for full tracebacks in CloudWatch

### Frontend

- Fetch errors display Hebrew error messages in the UI
- 401 responses trigger automatic redirect to login page
- 429 responses display rate limit message
- Network errors show: "שגיאת תקשורת. אנא בדוק את החיבור לאינטרנט."
- Loading overlay always hidden in `finally` block of fetch calls

## Logging

- Use Python `logging` module: `logger = logging.getLogger()` at module level
- Set level: `logger.setLevel(logging.INFO)`
- Log at entry points: `logger.info(f'Handler invoked: {method} {path}')`
- Log results: `logger.info(f'Found {len(results)} results')`
- Log errors with `exc_info=True`
- Log warnings for invalid input
- All logs go to CloudWatch Logs automatically

## Testing

- `unittest` framework with `unittest.mock` for mocking
- Test classes inherit `unittest.TestCase`
- `setUp` method for test fixtures
- Docstrings on test methods reference requirement IDs (e.g., `Validates: Requirements 2.8`)
- Arrange/Act/Assert pattern with comments
- Run with: `pytest tests/`

## Visual Design

### Color Palette

| Token | Value | Usage |
|---|---|---|
| Dark background | `#001D29` | Page background |
| Gold accent | `#DAA520` | Buttons, borders, highlights |
| Gold light | `#FFD700` | Gradients, hover states |
| Gold dark | `#B8860B` | Gradients, active states |
| Parchment | `#F5F5DC` | Text on dark backgrounds |
| Dark text | `#2D2D2D` | Text on light backgrounds |
| Deep blue | `#191970` | Headings, links |
| Navy | `#1e3a5f` | Buttons, cards |

### Effects

- Glassmorphism: `backdrop-filter: blur(20px) saturate(180%)` with semi-transparent backgrounds
- Animations: `@keyframes` for float, glow, fadeInUp, twinkle
- Transitions: `cubic-bezier(0.4, 0, 0.2, 1)` easing
- Hover: `translateY(-2px)` lift with enhanced box-shadow
- Focus: `outline: 2px solid #DAA520` with `outline-offset: 2px`

### Spacing and Sizing

- Border-radius: `8px` inputs, `16px` buttons/cards, `20px–24px` sections
- Responsive breakpoints: `768px` (mobile), `640px` (small mobile)
- Inline SVG icons: stroke-based, `viewBox="0 0 24 24"`
