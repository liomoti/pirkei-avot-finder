from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Mishna(db.Model):
    """
    Model representing a Mishna.

    Attributes:
        id (str): Unique identifier of the mishna, combining chapter and mishna (e.g., '1_1').
        chapter (str): The chapter number of the mishna.
        mishna (str): The mishna number within the chapter.
        number (int): Unique number for each mishna.
        text_pretty (str): The formatted content of the mishna.
        text_raw (str): The raw content of the mishna.
        interpretation (str): Optional interpretation or commentary for the mishna.
        tags (list[Tag]): A list of tags associated with the mishna.
    """
    __tablename__ = 'mishna'
    id = db.Column(db.String(100), primary_key=True)  # Unique ID combining chapter and mishna
    chapter = db.Column(db.String(50), nullable=False)
    mishna = db.Column(db.String(50), nullable=False)
    number = db.Column(db.SmallInteger, nullable=False, unique=True)  # Unique number for each mishna
    text_pretty = db.Column(db.String, nullable=False)
    text_raw = db.Column(db.String, nullable=False)
    interpretation = db.Column(db.Text)
    pirush_url = db.Column(db.Text, nullable=True, default=None)
    tags = db.relationship('Tag', secondary='mishna_tag', back_populates='mishnaiot')

    def __init__(self, chapter, mishna, number, text_pretty, text_raw, tags, interpretation="", pirush_url=None):
        self.chapter = chapter
        self.mishna = mishna
        self.number = number
        self.text_pretty = text_pretty
        self.text_raw = text_raw
        self.tags = tags
        self.interpretation = interpretation
        self.pirush_url = pirush_url or None
        # Create a unique id by combining chapter and mishna
        self.id = f"{chapter}_{mishna}"


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color = db.Column(db.String(7), nullable=False, default="#F5F5F5")  # Hex color code


class Tag(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))

    category = db.relationship('Category', backref=db.backref('tags', lazy=True))
    mishnaiot = db.relationship('Mishna', secondary='mishna_tag', back_populates='tags')

    @property
    def category_name(self):
        return self.category.name if self.category else "כללי"


class SiteSetting(db.Model):
    """
    Model for storing site-wide configuration as key-value pairs.

    Attributes:
        key (str): The setting key (primary key).
        value (str): The setting value.
    """
    __tablename__ = 'site_setting'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(255), nullable=False)


def get_pirush_settings():
    """Fetch pirush settings in a single DB query + config read.

    Returns:
        dict with keys 'pirush_enabled' (bool) and 'pirush_attribution_url' (str).
    """
    from flask import current_app
    setting = SiteSetting.query.filter_by(key='pirush_enabled').first()
    pirush_enabled = (setting.value == 'true') if setting else True
    pirush_attribution_url = current_app.config.get('PIRUSH_ATTRIBUTION_URL', '')
    return {
        'pirush_enabled': pirush_enabled,
        'pirush_attribution_url': pirush_attribution_url,
    }


def set_pirush_enabled(enabled):
    """Upsert the pirush_enabled setting."""
    setting = SiteSetting.query.filter_by(key='pirush_enabled').first()
    if setting is None:
        setting = SiteSetting(key='pirush_enabled', value='true' if enabled else 'false')
        db.session.add(setting)
    else:
        setting.value = 'true' if enabled else 'false'
    db.session.commit()


# Association table for the many-to-many relationship between Mishna and Tag
mishna_tag = db.Table(
    'mishna_tag',
    db.Column('mishna_id', db.String(100), db.ForeignKey('mishna.id'), primary_key=True),  # Foreign key updated to reference Mishna.id
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)
