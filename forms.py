from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField, SelectField, StringField, SelectMultipleField
from constants import ALLOWED_CHAPTERS
from models import Tag


class MishnaForm(FlaskForm):
    chapter = SelectField('פרק', choices=[], coerce=str)
    mishna = SelectField('מספר מִשׁנָה', choices=[], coerce=str)
    text = TextAreaField('טקסט המִשׁנָה')
    semantic_text = TextAreaField('טקסט סמנטי')
    tags = SelectMultipleField('תגיות', choices=[], coerce=int)
    submit = SubmitField('הוסף מִשׁנָה')

    def __init__(self, *args, **kwargs):
        super(MishnaForm, self).__init__(*args, **kwargs)

        # Populate the chapter dropdown
        self.chapter.choices = [(ch, ch) for ch in ALLOWED_CHAPTERS.keys()]

        # Populate tags dropdown with available tags
        self.tags.choices = [(tag.id, tag.name) for tag in Tag.query.all()]

        # If a chapter is selected, populate the mishna dropdown based on that chapter
        if self.chapter.data in ALLOWED_CHAPTERS:
            self.mishna.choices = [(mishna, mishna) for mishna in ALLOWED_CHAPTERS[self.chapter.data]]
        else:
            self.mishna.choices = []  # Initially empty if no chapter is selected


class TagForm(FlaskForm):
    name = StringField("שם התגית")
    submit = SubmitField("הוסף תגית")