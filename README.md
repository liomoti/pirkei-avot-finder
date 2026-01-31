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
- אפשרות לשיתוף תוצאות חיפוש
- חוויית משתמש מהירה ונוחה

האתר מיועד לסטודנטים, מורים, חוקרים וכל אדם המעוניין ללמוד ולחפש במסכת פרקי אבות בצורה יעילה ומתקדמת.

---

## Technical Overview (For Developers)

### Architecture & Stack

**Pirkei Avot Finder** is a production-grade Flask web application for semantic search and content management of Mishnayot from Pirkei Avot (Ethics of the Fathers).

#### Core Technologies:
- **Backend Framework**: Flask 3.1.0 with Blueprint-based modular architecture
- **Database**: PostgreSQL with pgvector extension for vector similarity search
- **ORM**: SQLAlchemy 2.0.35 with Flask-SQLAlchemy integration
- **Authentication**: Supabase Auth for secure admin access
- **Forms & Validation**: WTForms with Flask-WTF and CSRF protection
- **Production Server**: Gunicorn with optimized worker configuration
- **Containerization**: Docker with multi-stage builds
- **Deployment**: Render (cloud platform for web applications)

### Key Features

#### 1. **Multi-Modal Search System**
- **Chapter/Mishna Navigation**: Direct access to specific Mishnayot by ID
- **Exact Text Search**: SQL-based full-text search with niqqud normalization
- **Semantic AI Search**: AWS API Gateway integration with external ML service for context-aware Hebrew text search
- **Tag-Based Search**: Multi-tag filtering with categorized taxonomy
- **Mishna Number Navigation**: Direct jump to specific Mishna by sequential number (1-108)

#### 2. **Semantic Search Implementation**
The application integrates with an external AWS-hosted semantic search service:
- **Client**: `AWSSemanticSearchClient` handles authentication, request formatting, and response parsing
- **API Integration**: RESTful API with API key authentication
- **Result Processing**: Maps external API results back to local database records
- **Relevance Scoring**: Attaches similarity scores (0-100%) to search results

> **Note**: Local semantic search using AlephBERT (`sentence-transformers`) was disabled to reduce memory footprint. The code is preserved in `utils/semantic_search.py` for future reference.

#### 3. **Database Schema**
- **Mishna Model**: 
  - Composite ID (`chapter_mishna`)
  - Unique sequential number (1-108)
  - Dual text fields: `text_pretty` (with niqqud) and `text_raw` (normalized)
  - Many-to-many relationship with tags
  - Optional vector embedding field for semantic search (when enabled)
  
- **Tag Model**: Hierarchical tag system with categories
- **Category Model**: Color-coded tag categories for visual organization

#### 4. **Admin Content Management**
Supabase-authenticated admin interface for:
- Creating and editing Mishnayot
- Managing tag taxonomy and categories
- Associating tags with content
- Bulk operations on content

#### 5. **Performance Optimizations**
- **Rate Limiting**: Sliding window rate limiter (20 requests/minute)
- **Connection Pooling**: Optimized for low-memory environments (pool size: 2, max overflow: 3)
- **Lazy Loading**: Singleton pattern for expensive resources (AWS client)
- **Memory Management**: Reduced dependencies by disabling local ML models

#### 6. **Frontend**
- **Framework**: Alpine.js for reactive UI components
- **Styling**: Tailwind CSS with custom mystical Hebrew theme
- **Animations**: Lottie.js for loading animations
- **UX Features**: 
  - Dynamic form updates (chapter → mishna dropdown)
  - Multi-select tag interface
  - Color-coded tag categories
  - Responsive design for mobile/desktop

### Project Structure
```
pirkei-avot-finder/
├── api/
│   ├── aws_search_client.py      # AWS semantic search integration
│   └── supabase_client.py        # Supabase authentication
├── utils/
│   ├── semantic_search.py        # [DISABLED] Local semantic search engine
│   ├── rate_limiter.py           # Request rate limiting
│   └── text_utils.py             # Hebrew text normalization
├── templates/                    # Jinja2 templates
│   ├── index.html                # Main search interface
│   ├── manage_content.html       # Admin content management
│   └── ...
├── static/                       # CSS, images, assets
├── scripts/                      # Database setup and utilities
├── tests/                        # Unit tests
├── app.py                        # Application factory
├── routes.py                     # Blueprint with all route handlers
├── models.py                     # SQLAlchemy models
├── config.py                     # Configuration management
├── forms.py                      # WTForms definitions
├── logger.py                     # Logging setup
├── constants.py                  # Chapter/Mishna constants
└── requirements.txt              # Python dependencies
```

### Configuration & Deployment

#### Environment Variables:
- `DATABASE_URL`: PostgreSQL connection string (required)
- `SECRET_KEY`: Flask secret key for sessions and CSRF
- `AWS_SEARCH_AI_KEY`: API key for AWS semantic search
- `AWS_SEARCH_API_URL`: AWS API Gateway endpoint
- Supabase configuration (URL, API keys)

#### Deployment:
- **Platform**: Render (cloud platform with Docker and native Python support)
- **Database**: PostgreSQL with SSL (sslmode=require)
- **Workers**: 4 Gunicorn workers (configurable via `gunicorn.conf.py`)
- **Memory**: Optimized for 512MB RAM environments
- **Start Command**: `gunicorn --config gunicorn.conf.py app:app`

### Development & Testing
- Comprehensive logging with structured messages
- Test suite for AWS search client
- Development mode with Flask debug server
- Production mode with Gunicorn WSGI server

### Security
- CSRF protection on all forms
- Session-based authentication with Supabase
- Rate limiting on public endpoints
- SQL injection protection via SQLAlchemy ORM
- SSL/TLS for database connections

### Future Roadmap
- Re-enable local semantic search for offline capability
- Add user accounts and personalized collections
- Export search results to PDF/Word
- Advanced analytics dashboard for content insights
- Multi-language support (English translation)
