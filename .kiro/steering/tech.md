# Technology Stack

## Backend

- **Framework**: Flask 3.1.0 with Blueprint architecture
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLAlchemy 2.0.35 with Flask-SQLAlchemy
- **Production Server**: Gunicorn 21.2.0
- **Authentication**: Supabase Auth
- **Forms**: WTForms with Flask-WTF and CSRF protection

## External Services

- **AWS API Gateway**: Semantic search service with API key authentication
- **Supabase**: Authentication and session management

## Frontend

- **JavaScript**: Alpine.js for reactive components
- **CSS**: Tailwind CSS with custom Hebrew theme
- **Animations**: Lottie.js for loading states

## Deployment

- **Platform**: Render (cloud platform)
- **Container**: Docker with multi-stage builds
- **Database**: PostgreSQL with SSL (sslmode=require)
- **Memory**: Optimized for 512MB RAM environments

## Common Commands

### Development
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
# or
flask run
```

### Production
```bash
# Start with Gunicorn
gunicorn --config gunicorn.conf.py app:app
```

### Database
```bash
# Create database tables (run scripts)
python scripts/create_db.py

# Check memory usage
python scripts/check_memory.py
```

### Testing
```bash
# Run tests
pytest tests/
```

## Environment Variables

Required configuration in `.env`:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Flask secret key
- `AWS_SEARCH_AI_KEY`: API key for semantic search
- `AWS_SEARCH_API_URL`: AWS API Gateway endpoint
- Supabase credentials (URL, API keys)

## Performance Optimizations

- Connection pooling: pool_size=2, max_overflow=3
- Rate limiting: 20 requests/minute per IP
- Lazy loading for expensive resources (AWS client)
- SSL connection recycling every 5 minutes
