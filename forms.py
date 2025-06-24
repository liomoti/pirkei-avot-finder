from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField, SelectField, StringField, SelectMultipleField
from constants import ALLOWED_CHAPTERS
from models import Tag, Category


class MishnaForm(FlaskForm):
    chapter = SelectField('פרק', choices=[], coerce=str)
    mishna = SelectField('מִשׁנָה', choices=[], coerce=str)
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
    name = StringField("שם הנושא")
    category_id = SelectField("קטגוריה", choices=[], coerce=int)
    new_category_name = StringField("שם הקטגוריה החדשה")
    new_category_color = StringField("צבע הקטגוריה", default="#F5F5F5")
    tag_to_edit = SelectField("נושא לעריכה", choices=[], coerce=int)
    new_category_id = SelectField("קטגוריה חדשה", choices=[], coerce=int)
    submit = SubmitField("הוסף נושא")

    def __init__(self, *args, **kwargs):
        super(TagForm, self).__init__(*args, **kwargs)
        # Populate categories dropdown
        categories = Category.query.all()
        category_choices = [(0, "כללי")] + [(c.id, c.name) for c in categories]
        self.category_id.choices = category_choices
        self.new_category_id.choices = category_choices
        
        # Populate tags dropdown
        all_tags = Tag.query.all()
        self.tag_to_edit.choices = [(tag.id, f"{tag.name} ({tag.category.name if tag.category else 'כללי'})") for tag in all_tags]