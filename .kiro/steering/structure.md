# Project Structure

## Root Level

- `app.py`: Application factory and entry point
- `routes.py`: Blueprint with all route handlers
- `models.py`: SQLAlchemy database models
- `forms.py`: WTForms definitions
- `config.py`: Configuration management and environment variables
- `constants.py`: Chapter/Mishna constants
- `logger.py`: Logging setup
- `requirements.txt`: Python dependencies
- `gunicorn.conf.py`: Gunicorn production server configuration
- `Dockerfile`: Container configuration

## Directory Organization

### `/api`
External service integrations:
- `aws_search_client.py`: AWS semantic search API client
- `supabase_client.py`: Supabase authentication client

### `/utils`
Utility modules:
- `semantic_search.py`: [DISABLED] Local AlephBERT semantic search (preserved for reference)
- `rate_limiter.py`: Request rate limiting with sliding window
- `text_utils.py`: Hebrew text normalization (niqqud removal)

### `/templates`
Jinja2 HTML templates:
- `index.html`: Main search interface
- `manage_content.html`: Admin content management
- `manage_mishnas.html`: Mishna management
- `manage_tags.html`: Tag management
- `login.html`: Authentication page
- `result.html`: Search results display
- `error.html`: Error page
- `color_legend.html`: Tag category legend

### `/static`
Frontend assets:
- `style.css`: Custom styles
- `/pics`: Images, logos, SVG icons, Lottie animations

### `/scripts`
Database and utility scripts:
- `create_db.py`: Database initialization
- `create_db_sql`: SQL schema
- `raw_data_split.py`: Data processing
- `check_memory.py`: Memory monitoring

### `/tests`
Test suite:
- `__init__.py`: Test package initialization
- `test_aws_search_client.py`: AWS client tests

### `/docs`
Documentation:
- `TESTING_CHECKLIST.md`: Testing guidelines

## Architecture Patterns

### Blueprint Pattern
Single `main` blueprint in `routes.py` contains all route handlers, keeping the application modular.

### Lazy Loading
Expensive resources (AWS client, semantic search engine) use singleton pattern with lazy initialization to reduce memory footprint.

### Database Models
- `Mishna`: Composite ID (`chapter_mishna`), unique sequential number, dual text fields (pretty/raw)
- `Tag`: Hierarchical with category relationship
- `Category`: Color-coded tag categories
- `mishna_tag`: Many-to-many association table

### Form Handling
WTForms with dynamic choices populated from database, CSRF protection enabled on all forms.

### Error Handling
Comprehensive logging with structured messages, graceful error pages, database rollback on failures.

## Code Conventions

- Hebrew text normalization: Use `remove_niqqud()` for search operations
- Logging: Use `current_app.logger` with appropriate levels (info, warning, error)
- Database operations: Always wrap in try/except with rollback on SQLAlchemyError
- Rate limiting: Apply `@rate_limit` decorator to public endpoints
- Authentication: Use `@login_is_required` decorator for admin routes
