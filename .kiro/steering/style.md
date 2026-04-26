# Code Style Guide

## Python

### General
- No type hints on most functions (except API client classes which use them)
- Single quotes for strings, f-strings for interpolation
- Module-level docstrings with triple double-quotes on multi-line blocks
- Class docstrings describe attributes in Google-style format
- Inline comments in English; user-facing strings in Hebrew
- Blank line between logical sections within functions
- Commented-out code is preserved with section headers using `# ===` banners when disabling features

### Naming
- `snake_case` for variables, functions, modules
- `PascalCase` for classes and exceptions
- `UPPER_SNAKE_CASE` for constants and config values
- Private/internal functions prefixed with `_` (e.g., `_make_api_request`)
- Global singletons prefixed with `_` (e.g., `_aws_search_client`)

### Imports
- Standard library first, then third-party, then local — separated by blank lines
- Relative imports for local modules (`from models import db, Mishna`)
- No `__all__` exports

### Functions & Methods
- Lazy-loading singletons via module-level `get_*` functions with `global` keyword
- Decorators for cross-cutting concerns: `@login_is_required`, `@rate_limit`, `@wraps`
- Route handlers follow pattern: validate → query → process → render
- Database writes always wrapped in `try/except SQLAlchemyError` with `db.session.rollback()`

### Logging
- Use `current_app.logger` (never `logging.getLogger`)
- Log at entry points: `current_app.logger.info(f'Action initiated: {action}')`
- Log results: `current_app.logger.info(f'Found {len(results)} results')`
- Log errors with `exc_info=True` for tracebacks
- Log warnings for invalid input or rate limit hits

### Error Handling
- Outer `try/except Exception` in route handlers with generic error page fallback
- Inner `try/except SQLAlchemyError` for database operations
- Custom exception classes for API clients (e.g., `AWSSearchError`)
- User-facing error messages in Hebrew

### Testing
- `unittest` framework with `unittest.mock` for mocking
- Test classes inherit `unittest.TestCase`
- `setUp` method for test fixtures
- Docstrings on test methods reference requirement IDs (e.g., `Validates: Requirements 3.1`)
- Arrange/Act/Assert pattern with comments

## HTML / Jinja2

### Structure
- Full HTML5 documents with `<!DOCTYPE html>`, `<html lang="he" dir="rtl">`
- Tailwind CSS via CDN (`cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19`)
- Alpine.js via CDN for reactive components (`x-data`, `x-show`, `x-cloak`, `@click`)
- Custom CSS in `/static/style.css`, inline `<style>` blocks for page-specific animations
- Jinja2 template variables: `{{ variable }}`, `{% if %}`, `{% for %}`
- CSRF token via `{{ form.hidden_tag() }}`

### Patterns
- Inline SVG icons (no icon library) — stroke-based, `viewBox="0 0 24 24"`
- Tailwind utility classes for layout, spacing, typography
- Custom CSS classes for themed components: `.content-overlay`, `.search-section-blue`, `.search-section-dark`, `.search-section-parchment`, `.result-card`, `.header-mystical`, `.footer-ancient`
- Alpine.js `x-data` on body or container for page-level state
- Form actions determined by hidden `action` input field, not separate routes

## CSS

### Theme
- Dark background: `#001D29`
- Gold accent: `#DAA520`, `#B8860B`, `#FFD700`
- Parchment text: `#F5F5DC`, `#2D2D2D`
- Deep blue: `#191970`, `#1e3a5f`
- Navy buttons: `#1e3a5f` background, `#f4e8d0` text

### Patterns
- Glassmorphism: `backdrop-filter: blur(20px) saturate(180%)` with semi-transparent backgrounds
- `!important` used extensively to override Tailwind defaults
- CSS custom animations: `@keyframes` for float, glow, fadeInUp, twinkle effects
- Transitions use `cubic-bezier(0.4, 0, 0.2, 1)` easing
- Responsive breakpoints: `768px` (mobile), `640px` (small mobile)
- Hover effects: `translateY(-2px)` lift, scale, enhanced box-shadow
- Focus states: `outline: 2px solid #DAA520` with `outline-offset: 2px`
- Border-radius: `8px` for inputs, `16px` for buttons/cards, `20px–24px` for sections

### Conventions
- Section comments with `/* ===== SECTION NAME ===== */`
- Properties grouped: positioning → display → box model → typography → visual → animation
- Multiple `body {}` blocks (additive, not conflicting)
- Pseudo-elements (`::before`, `::after`) for texture overlays
