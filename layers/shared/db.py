import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Read connection string from environment (supports both direct and pooled Supabase endpoints)
DATABASE_URL = os.environ['DATABASE_URL']

# Engine initialized at module level — persists across warm Lambda invocations.
# pool_size=1 and max_overflow=0 ensure a single connection per Lambda container.
# pool_pre_ping=True verifies the connection is alive before each use.
# pool_recycle=300 refreshes connections every 5 minutes to avoid stale SSL sessions.
engine = create_engine(
    DATABASE_URL,
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={'sslmode': 'require'}
)

Session = sessionmaker(bind=engine)
