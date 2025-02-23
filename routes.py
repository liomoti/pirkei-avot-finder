from functools import wraps
from flask import Blueprint, render_template, request, current_app, redirect, session
from sqlalchemy.exc import SQLAlchemyError

from api.supabase_client import supabase
from constants import ALLOWED_CHAPTERS
from forms import MishnaForm, TagForm
from models import db, Mishna, Tag
from utils.text_utils import remove_niqqud

# Define the blueprint
main = Blueprint('main', __name__)

# ~~~~~~~~~~~~~~~~~~~~~~~~~ Authentication ~~~~~~~~~~~~~~~~~~~~~
def login_is_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("access_token"):
            return render_template('login.html')
        return function(*args, **kwargs)
    return wrapper

@main.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            # Authenticate with Supabase
            auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if auth_response.user:  # Check if authentication was successful
                session['access_token'] = auth_response.session.access_token
                return redirect("manage", code=302)
        except (Exception,) as e:
            return render_template('login.html')
    return render_template('login.html')

@main.route("/logout", methods=['POST'])
def logout():
    # session.pop('access_token', None)
    session.clear()
    return redirect("/", code=302)

@main.route('/', methods=['GET', 'POST'])
def search_mishna():
    """Handle mishna search functionality."""
    try:
        mishna_form = MishnaForm(request.form)
        results = []
        selected_tags = []
        all_tags = Tag.query.all()
        search_type = request.form.get('search_type', 'search_mishna')

        if request.method == 'POST':
            action = request.form.get('action')
            current_app.logger.info(f'Search action initiated: {action}')

            # Search by Chapter and Mishna
            if action == 'search_mishna':
                chapter = mishna_form.chapter.data
                mishna = mishna_form.mishna.data
                # current_app.logger.info(f'Searching for Mishna - Chapter: {chapter}, Mishna: {mishna}')

                mishna_id = f"{chapter}_{mishna}"
                results = Mishna.query.filter_by(id=mishna_id).all()

                # if results:
                #     current_app.logger.info(f'Found {len(results)} results for Chapter {chapter}, Mishna {mishna}')
                # else:
                #     current_app.logger.info(f'No results found for Chapter {chapter}, Mishna {mishna}')

            # Free Text Search
            elif action == 'search_free_text':
                query_text = remove_niqqud(mishna_form.text.data.lower())
                current_app.logger.info(f'Performing free text search with query: {query_text}')

                results = Mishna.query.filter(Mishna.text_raw.ilike(f"%{query_text}%")).all()
                current_app.logger.info(f'Found {len(results)} results for free text search')

            # Tag-based Search
            elif action == 'search_by_tags':
                selected_tags = request.form.get('tags', '').split(',')
                selected_tags = [int(tag_id) for tag_id in selected_tags if tag_id.isdigit()]
                current_app.logger.info(f'Searching by tags: {selected_tags}')

                results = Mishna.query.filter(Mishna.tags.any(Tag.id.in_(selected_tags))).all()
                current_app.logger.info(f'Found {len(results)} results for tag-based search')

        return render_template('index.html',
                               form=mishna_form,
                               results=results,
                               searchType=search_type,
                               ALLOWED_CHAPTERS=ALLOWED_CHAPTERS,
                               all_tags=all_tags,
                               selected_tags=selected_tags,
                               selected_chapter=mishna_form.chapter.data,
                               selected_mishna=mishna_form.mishna.data)

    except Exception as e:
        current_app.logger.error(f'Error in search_mishna: {str(e)}', exc_info=True)
        # You might want to show an error page to the user here
        return render_template('error.html', error="An error occurred during search")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Front ~~~~~~~~~~~~~~~~~~~~~~~~~~~
@main.route('/manage', methods=['GET', 'POST'])
@login_is_required
def manage_content():
    """Handle content management functionality."""
    try:
        mishna_form = MishnaForm(request.form)
        tag_form = TagForm(request.form)

        tag_message = None
        mishna_message = None
        button_label = 'הוסף משנה'
        all_tags = Tag.query.all()
        selected_tags = []

        if request.method == 'POST':
            action = request.form.get('action')
            current_app.logger.info(f'Content management action initiated: {action}')

            # Search Mishna
            if action == 'search_mishna':
                chapter = mishna_form.chapter.data
                mishna = mishna_form.mishna.data
                current_app.logger.info(f'Searching for existing Mishna - Chapter: {chapter}, Mishna: {mishna}')

                mishna_id = f"{chapter}_{mishna}"
                existing_mishna = Mishna.query.filter_by(id=mishna_id).first()

                if existing_mishna:
                    mishna_form.text.data = existing_mishna.text_pretty
                    selected_tags = [tag.id for tag in existing_mishna.tags]
                    mishna_message = f"מִשׁנָה בפרק {chapter} משנה {mishna} קיימת במאגר."
                    button_label = 'עדכן משנה'
                    current_app.logger.info(f'Found existing Mishna: {mishna_id}')
                else:
                    mishna_form.text.data = ''
                    selected_tags = []
                    mishna_message = f"מִשׁנָה בפרק {chapter} משנה {mishna} לא קיימת במאגר."
                    current_app.logger.info(f'Mishna not found: {mishna_id}')

            # Submit Mishna
            elif action == 'submit_mishna':
                try:
                    chapter = mishna_form.chapter.data
                    mishna = mishna_form.mishna.data
                    text_pretty = mishna_form.text.data
                    text_raw = remove_niqqud(text_pretty)
                    current_app.logger.info(
                        f'Attempting to submit/update Mishna - Chapter: {chapter}, Mishna: {mishna}')

                    selected_tags = request.form.get('tags')
                    selected_tags = [int(tag_id) for tag_id in selected_tags.split(",") if
                                     tag_id] if selected_tags else []
                    new_tags = Tag.query.filter(Tag.id.in_(selected_tags)).all()

                    mishna_id = f"{chapter}_{mishna}"
                    existing_mishna = Mishna.query.filter_by(id=mishna_id).first()

                    if existing_mishna:
                        current_app.logger.info(f'Updating existing Mishna: {mishna_id}')
                        existing_mishna.text_pretty = text_pretty
                        existing_mishna.text_raw = text_raw
                        existing_mishna.tags = new_tags
                        mishna_message = "המִשׁנָה עודכנה בהצלחה!"
                    else:
                        current_app.logger.info(f'Creating new Mishna: {mishna_id}')
                        new_mishna = Mishna(chapter=chapter,
                                            mishna=mishna,
                                            text_pretty=text_pretty,
                                            text_raw=text_raw,
                                            tags=new_tags,
                                            interpretation="")
                        db.session.add(new_mishna)
                        mishna_message = "המִשׁנָה הוספה בהצלחה!"

                    db.session.commit()
                    current_app.logger.info('Database transaction completed successfully')

                except SQLAlchemyError as e:
                    db.session.rollback()
                    current_app.logger.error(f'Database error while submitting Mishna: {str(e)}', exc_info=True)
                    mishna_message = "אירעה שגיאה בשמירת המשנה"

            # Handle Tags
            elif action == "add_tag":
                new_tag_name = tag_form.name.data
                current_app.logger.info(f'Attempting to add new tag: {new_tag_name}')

                if new_tag_name:
                    existing_tag = Tag.query.filter_by(name=new_tag_name).first()
                    if not existing_tag:
                        try:
                            new_tag = Tag(name=new_tag_name)
                            db.session.add(new_tag)
                            db.session.commit()
                            tag_message = "התגית הוספה בהצלחה!"
                            current_app.logger.info(f'Successfully added new tag: {new_tag_name}')
                        except SQLAlchemyError as e:
                            db.session.rollback()
                            current_app.logger.error(f'Database error while adding tag: {str(e)}', exc_info=True)
                            tag_message = "אירעה שגיאה בהוספת התגית"
                    else:
                        current_app.logger.info(f'Tag already exists: {new_tag_name}')
                        tag_message = "התגית כבר קיימת."

            elif action == "delete_tag":
                tag_id_to_delete = request.form.get('tag_to_delete')
                current_app.logger.info(f'Attempting to delete tag ID: {tag_id_to_delete}')

                if tag_id_to_delete:
                    try:
                        existing_tag = Tag.query.filter_by(id=tag_id_to_delete).first()
                        if existing_tag:
                            db.session.delete(existing_tag)
                            db.session.commit()
                            tag_message = "התגית נמחקה."
                            current_app.logger.info(f'Successfully deleted tag ID: {tag_id_to_delete}')
                        else:
                            current_app.logger.warning(f'Tag not found for deletion: {tag_id_to_delete}')
                            tag_message = "לא הצלחנו למצוא את התגית במאגר."
                    except SQLAlchemyError as e:
                        db.session.rollback()
                        current_app.logger.error(f'Database error while deleting tag: {str(e)}', exc_info=True)
                        tag_message = "אירעה שגיאה במחיקת התגית"
                else:
                    current_app.logger.warning('No tag ID provided for deletion')
                    tag_message = "בחר תגית למחיקה."

        return render_template('manage_content.html',
                               mishna_form=mishna_form,
                               tag_form=tag_form,
                               tag_message=tag_message,
                               mishna_message=mishna_message,
                               button_label=button_label,
                               ALLOWED_CHAPTERS=ALLOWED_CHAPTERS,
                               all_tags=all_tags,
                               selected_tags=selected_tags,
                               selected_chapter=mishna_form.chapter.data,
                               selected_mishna=mishna_form.mishna.data)

    except Exception as e:
        current_app.logger.error(f'Unexpected error in manage_content: {str(e)}', exc_info=True)
        return render_template('error.html', error="An error occurred while managing content")
