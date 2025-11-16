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

    # SQLAlchemy Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection Pooling - optimized for low-memory environments
    SQLALCHEMY_POOL_SIZE = 2
    SQLALCHEMY_MAX_OVERFLOW = 3
    SQLALCHEMY_POOL_RECYCLE = 300  # Recycle connections after 5 minutes
    SQLALCHEMY_POOL_PRE_PING = True  # Verify connections before using

    # SSL Configuration for cloud databases
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'sslmode': 'require'
        }
    }
