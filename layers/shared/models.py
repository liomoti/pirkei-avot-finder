import os
from datetime import datetime, timezone

from sqlalchemy import Column, String, SmallInteger, Integer, Text, DateTime, ForeignKey, Table, UniqueConstraint, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Association table for the many-to-many relationship between Mishna and Tag
mishna_tag = Table(
    'mishna_tag', Base.metadata,
    Column('mishna_id', String(100), ForeignKey('mishna.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True)
)


class Mishna(Base):
    """
    Model representing a Mishna.

    Attributes:
        id (str): Unique identifier of the mishna, combining chapter and mishna (e.g., 'א_ב').
        chapter (str): The chapter number of the mishna.
        mishna (str): The mishna number within the chapter.
        number (int): Unique number for each mishna.
        text_pretty (str): The formatted content of the mishna.
        text_raw (str): The raw content of the mishna.
        interpretation (str): Optional interpretation or commentary for the mishna.
        pirush_url (str): Optional URL for pirush commentary.
        tags (list[Tag]): A list of tags associated with the mishna.
    """
    __tablename__ = 'mishna'
    id = Column(String(100), primary_key=True)  # Unique ID combining chapter and mishna
    chapter = Column(String(50), nullable=False)
    mishna = Column(String(50), nullable=False)
    number = Column(SmallInteger, nullable=False, unique=True)  # Unique number for each mishna
    text_pretty = Column(String, nullable=False)
    text_raw = Column(String, nullable=False)
    interpretation = Column(Text)
    pirush_url = Column(Text, nullable=True, default=None)
    tags = relationship('Tag', secondary=mishna_tag, back_populates='mishnaiot')

    def __init__(self, chapter, mishna, number, text_pretty, text_raw, tags, interpretation='', pirush_url=None):
        self.chapter = chapter
        self.mishna = mishna
        self.number = number
        self.text_pretty = text_pretty
        self.text_raw = text_raw
        self.tags = tags
        self.interpretation = interpretation
        self.pirush_url = pirush_url or None
        # Create a unique id by combining chapter and mishna
        self.id = f'{chapter}_{mishna}'


class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(7), nullable=False, default='#F5F5F5')  # Hex color code


class Tag(Base):
    """
    Model representing a Tag.

    Attributes:
        id (int): The unique identifier of the tag.
        name (str): The name of the tag.
        category_id (int): The ID of the associated category.
        category (Category): The category this tag belongs to.
        mishnaiot (list[Mishna]): A list of mishnaiot associated with this tag.
    """
    __tablename__ = 'tag'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    category_id = Column(Integer, ForeignKey('categories.id'))

    category = relationship('Category', backref='tags')
    mishnaiot = relationship('Mishna', secondary=mishna_tag, back_populates='tags')

    @property
    def category_name(self):
        return self.category.name if self.category else 'כללי'


class SiteSetting(Base):
    """
    Model for storing site-wide configuration as key-value pairs.

    Attributes:
        key (str): The setting key (primary key).
        value (str): The setting value.
    """
    __tablename__ = 'site_setting'
    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)


def get_pirush_settings(session):
    """Fetch pirush settings in a single DB query + env var read.

    Args:
        session: SQLAlchemy session instance.

    Returns:
        dict with keys 'pirush_enabled' (bool) and 'pirush_attribution_url' (str).
    """
    setting = session.query(SiteSetting).filter_by(key='pirush_enabled').first()
    pirush_enabled = (setting.value == 'true') if setting else True
    pirush_attribution_url = os.environ.get('PIRUSH_ATTRIBUTION_URL', 'https://www.veten.co.il')
    return {
        'pirush_enabled': pirush_enabled,
        'pirush_attribution_url': pirush_attribution_url,
    }


def set_pirush_enabled(session, enabled):
    """Upsert the pirush_enabled setting.

    Args:
        session: SQLAlchemy session instance.
        enabled: Boolean indicating whether pirush is enabled.
    """
    setting = session.query(SiteSetting).filter_by(key='pirush_enabled').first()
    if setting is None:
        setting = SiteSetting(key='pirush_enabled', value='true' if enabled else 'false')
        session.add(setting)
    else:
        setting.value = 'true' if enabled else 'false'
    session.commit()


class UserFavorite(Base):
    """
    Model representing a user's saved favorite Mishna.

    Attributes:
        id (int): Auto-incremented primary key.
        user_sub (str): Cognito user sub (UUID) identifying the user.
        mishna_id (str): Foreign key reference to the Mishna.
        created_at (datetime): UTC timestamp when the favorite was added.
        mishna (Mishna): The associated Mishna object (eager-loaded).
    """
    __tablename__ = 'user_favorite'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_sub = Column(String(128), nullable=False, index=True)
    mishna_id = Column(String(100), ForeignKey('mishna.id'), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    mishna = relationship('Mishna', lazy='joined')

    __table_args__ = (
        UniqueConstraint('user_sub', 'mishna_id', name='uq_user_favorite'),
    )


class UserLearned(Base):
    """
    Model representing a user's learned Mishna record.

    Attributes:
        id (int): Auto-incremented primary key.
        user_sub (str): Cognito user sub (UUID) identifying the user.
        mishna_id (str): Foreign key reference to the Mishna.
        created_at (datetime): UTC timestamp when the Mishna was marked as learned.
        mishna (Mishna): The associated Mishna object (eager-loaded).
    """
    __tablename__ = 'user_learned'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_sub = Column(String(128), nullable=False, index=True)
    mishna_id = Column(String(100), ForeignKey('mishna.id'), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    mishna = relationship('Mishna', lazy='joined')

    __table_args__ = (
        UniqueConstraint('user_sub', 'mishna_id', name='uq_user_learned'),
    )


class AiSearchLog(Base):
    """
    Model representing a logged AI/semantic search query for admin analytics.

    Attributes:
        id (int): Auto-incremented primary key.
        query_text (str): The semantic search query string.
        result_count (int): Number of results returned.
        result_ids (str): Comma-separated mishna IDs from results (nullable).
        user_sub (str): Cognito user sub if authenticated, NULL otherwise.
        created_at (datetime): UTC timestamp when the search was performed.
    """
    __tablename__ = 'ai_search_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(String(500), nullable=False)
    result_count = Column(Integer, nullable=False, default=0)
    result_ids = Column(Text, nullable=True)
    user_sub = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_ai_search_log_created', 'created_at'),
    )
