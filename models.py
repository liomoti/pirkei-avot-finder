from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()


class Mishna(db.Model):
    """
    Model representing a Mishna.

    Attributes:
        id (str): Unique identifier of the mishna, combining chapter and mishna (e.g., '1_1').
        chapter (str): The chapter number of the mishna.
        mishna (str): The mishna number within the chapter.
        text_pretty (str): The formatted content of the mishna.
        text_raw (str): The raw content of the mishna.
        interpretation (str): Optional interpretation or commentary for the mishna.
        tags (list[Tag]): A list of tags associated with the mishna.
        embedding (list[float]): A vector representation of the mishna for machine learning purposes.
    """
    __tablename__ = 'mishna'
    id = db.Column(db.String(100), primary_key=True)  # Unique ID combining chapter and mishna
    chapter = db.Column(db.String(50), nullable=False)
    mishna = db.Column(db.String(50), nullable=False)
    text_pretty = db.Column(db.String, nullable=False)
    text_raw = db.Column(db.String, nullable=False)
    interpretation = db.Column(db.Text)
    embedding = db.Column(Vector(768))
    tags = db.relationship('Tag', secondary='mishna_tag', back_populates='mishnaiot')

    def __init__(self, chapter, mishna, text_pretty, text_raw, tags, interpretation="", embedding=None):
        self.chapter = chapter
        self.mishna = mishna
        self.text_pretty = text_pretty
        self.text_raw = text_raw
        self.tags = tags
        self.interpretation = interpretation
        self.embedding = embedding
        # Create a unique id by combining chapter and mishna
        self.id = f"{chapter}_{mishna}"


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


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


# Association table for the many-to-many relationship between Mishna and Tag
mishna_tag = db.Table(
    'mishna_tag',
    db.Column('mishna_id', db.String(100), db.ForeignKey('mishna.id'), primary_key=True),  # Foreign key updated to reference Mishna.id
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)
