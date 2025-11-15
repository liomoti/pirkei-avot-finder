import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # SECRET_KEY = ''
    # SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "data", "pirkei_avot.db")}'
    # SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Require DATABASE_URL to be set
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("No DATABASE_URL set for PostgreSQL connection")

    # Ensure the connection string uses postgresql:// prefix
    SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback_secret_key_for_development')
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens (or set to seconds like 3600)

    # SQLAlchemy Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection Pooling
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20

    # SSL Configuration for cloud databases
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'sslmode': 'require'
        }
    }

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_SEARCH = 20  # requests per minute for search
    RATE_LIMIT_SEMANTIC = 10  # requests per minute for semantic search (more expensive)
    RATE_LIMIT_WINDOW = 60  # seconds
