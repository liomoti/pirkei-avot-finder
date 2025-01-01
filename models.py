from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Mishna(db.Model):
    """
    Model representing a Mishna.

    Attributes:
        id (str): Unique identifier of the mishna, combining chapter and mishna (e.g., '1_1').
        chapter (str): The chapter number of the mishna.
        mishna (str): The mishna number within the chapter.
        text (str): The content of the mishna.
        tags (list[Tag]): A list of tags associated with the mishna.
    """
    id = db.Column(db.String(100), primary_key=True)  # Unique ID combining chapter and mishna
    chapter = db.Column(db.String(50), nullable=False)
    mishna = db.Column(db.String(50), nullable=False)
    text_pretty = db.Column(db.String, nullable=False)
    text_raw = db.Column(db.String, nullable=False)
    interpretation = db.Column(db.Text)
    tags = db.relationship('Tag', secondary='mishna_tag', back_populates='mishnaiot')

    def __init__(self, chapter, mishna, text_pretty, text_raw, tags, interpretation=""):
        self.chapter = chapter
        self.mishna = mishna
        self.text_pretty = text_pretty
        self.text_raw = text_raw
        self.tags = tags
        self.interpretation = interpretation
        # Create a unique id by combining chapter and mishna
        self.id = f"{chapter}_{mishna}"


class Tag(db.Model):
    """
    Model representing a Tag.

    Attributes:
        id (int): The unique identifier of the tag.
        name (str): The name of the tag.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    mishnaiot = db.relationship('Mishna', secondary='mishna_tag', back_populates='tags')


# Association table for the many-to-many relationship between Mishna and Tag
mishna_tag = db.Table(
    'mishna_tag',
    db.Column('mishna_id', db.String(100), db.ForeignKey('mishna.id'), primary_key=True),  # Foreign key updated to reference Mishna.id
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)
