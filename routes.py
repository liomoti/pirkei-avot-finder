from functools import wraps
from flask import Blueprint, render_template, request, current_app, redirect, session
from flask_wtf.csrf import generate_csrf
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from api.supabase_client import supabase
from api.aws_search_client import AWSSemanticSearchClient, AWSSearchError
from constants import ALLOWED_CHAPTERS
from forms import MishnaForm, TagForm
from models import db, Mishna, Tag, Category
from utils.text_utils import remove_niqqud
from utils.rate_limiter import rate_limit
import os

# ============================================================================
# AI/Semantic Search - COMMENTED OUT (not in use)
# ============================================================================
# The semantic search functionality has been disabled to reduce memory usage.
# To re-enable: uncomment the code below and install sentence-transformers
# ============================================================================

# # Semantic search imports
# from sentence_transformers import SentenceTransformer
# from utils.semantic_search import SemanticSearchEngine
# 
# # Lazy-load the model only when needed to save memory
# _model = None
# _semantic_search_engine = None
# 
# def get_semantic_search_engine():
#     """Lazy-load the semantic search engine to save memory."""
#     global _model, _semantic_search_engine
#     if _semantic_search_engine is None:
#         current_app.logger.info('Loading AlephBERT model for semantic search...')
#         _model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')
#         _semantic_search_engine = SemanticSearchEngine(_model)
#         current_app.logger.info('Model loaded successfully')
#     return _semantic_search_engine

# ============================================================================
# AWS Semantic Search Client - Lazy Loading Singleton
# ============================================================================

_aws_search_client = None

def get_aws_search_client() -> AWSSemanticSearchClient:
    """
    Lazy-load AWS search client singleton.
    
    Returns:
        Initialized AWSSemanticSearchClient instance
        
    Raises:
        ValueError: If AWS_SEARCH_AI_KEY environment variable is not set
    """
    global _aws_search_client
    if _aws_search_client is None:
        api_key = os.getenv('AWS_SEARCH_AI_KEY')
        if not api_key:
            raise ValueError('AWS_SEARCH_AI_KEY environment variable not set')
        
        api_url = os.getenv('AWS_SEARCH_API_URL', 
                           'https://default-api-gateway-url.amazonaws.com/search')
        
        _aws_search_client = AWSSemanticSearchClient(api_key, api_url)
    
    return _aws_search_client

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
@rate_limit(max_requests=20, window_seconds=60)  # 20 requests per minute
def search_mishna():
    """Handle mishna search functionality."""
    try:
        mishna_form = MishnaForm(request.form)
        results = []
        selected_tags = []
        all_tags = Tag.query.all()
        tags_with_categories = [{"id": tag.id, "name": tag.name, "category": tag.category_name} for tag in all_tags]
        search_type = request.form.get('search_type', 'search_mishna')

        # Fetch categories for color legend
        categories = Category.query.all()
        categories_serialized = [
            {"id": c.id, "name": c.name, "color": c.color} for c in categories
        ]

        if request.method == 'POST':
            action = request.form.get('action')
            current_app.logger.info(f'Search action initiated: {action}')

            # Search by Chapter and Mishna
            if action == 'search_mishna':
                chapter = mishna_form.chapter.data
                mishna = mishna_form.mishna.data
                # If 'כל המשניות' (all) is selected, fetch all mishnas for the chapter
                if mishna == 'all':
                    results = Mishna.query.filter_by(chapter=chapter).order_by(Mishna.number).all()
                else:
                    mishna_id = f"{chapter}_{mishna}"
                    results = Mishna.query.filter_by(id=mishna_id).all()

            # Smart Search - Unified Free Text and AI Search
            elif action == 'search_smart':
                query_text = request.form.get('search_query', '').strip()
                is_exact_match = request.form.get('exact_match') == 'on'
                
                current_app.logger.info(f'Smart search initiated. Query: {query_text}, Exact Match: {is_exact_match}')
                
                if is_exact_match:
                    # LOGIC A: Exact Match - Use SQL/Supabase search
                    query_text_normalized = remove_niqqud(query_text.lower())
                    current_app.logger.info(f'Performing exact match search with normalized query length: {len(query_text_normalized)} characters')
                    
                    results = Mishna.query.filter(
                        Mishna.text_raw.ilike(f"%{query_text_normalized}%")
                    ).order_by(Mishna.number).all()
                    current_app.logger.info(f'Found {len(results)} results for exact match search')
                else:
                    # LOGIC B: AI Search - Use AWS Semantic Search
                    current_app.logger.info(f'Performing AWS semantic search with query length: {len(query_text)} characters')
                    
                    try:
                        # Initialize client (lazy loading)
                        client = get_aws_search_client()
                        results = client.search(query_text)
                        
                        current_app.logger.info(f'AWS semantic search returned {len(results)} results')
                        
                    except AWSSearchError as e:
                        current_app.logger.error(f'AWS search failed: {str(e)}')
                        return render_template('error.html', 
                                             error="חיפוש סמנטי נכשל. אנא נסה שוב מאוחר יותר.")
                    except ValueError as e:
                        current_app.logger.error(f'AWS search configuration error: {str(e)}')
                        return render_template('error.html', 
                                             error="חיפוש סמנטי אינו מוגדר כראוי. אנא פנה למנהל המערכת.")

            # Free Text Search (DEPRECATED - kept for backward compatibility)
            elif action == 'search_free_text':
                query_text = remove_niqqud(mishna_form.text.data.lower())
                current_app.logger.info(f'Performing free text search with query length: {len(query_text)} characters')

                results = Mishna.query.filter(Mishna.text_raw.ilike(f"%{query_text}%")).order_by(Mishna.number).all()
                current_app.logger.info(f'Found {len(results)} results for free text search')

            # Tag-based Search
            elif action == 'search_by_tags':
                selected_tags = request.form.get('tags', '').split(',')
                selected_tags = [int(tag_id) for tag_id in selected_tags if tag_id.isdigit()]
                current_app.logger.info(f'Searching by tags: {selected_tags}')

                results = Mishna.query.filter(Mishna.tags.any(Tag.id.in_(selected_tags))).order_by(Mishna.number).all()
                current_app.logger.info(f'Found {len(results)} results for tag-based search')

            # AWS Semantic Search (DEPRECATED - kept for backward compatibility)
            elif action == 'search_aws_semantic':
                query_text = request.form.get('aws_semantic_query', '').strip()
                current_app.logger.info(f'Performing AWS semantic search with query length: {len(query_text)} characters')
                
                try:
                    # Initialize client (lazy loading)
                    client = get_aws_search_client()
                    results = client.search(query_text)
                    
                    current_app.logger.info(f'AWS semantic search returned {len(results)} results')
                    
                except AWSSearchError as e:
                    current_app.logger.error(f'AWS search failed: {str(e)}')
                    return render_template('error.html', 
                                         error="חיפוש סמנטי נכשל. אנא נסה שוב מאוחר יותר.")
                except ValueError as e:
                    current_app.logger.error(f'AWS search configuration error: {str(e)}')
                    return render_template('error.html', 
                                         error="חיפוש סמנטי אינו מוגדר כראוי. אנא פנה למנהל המערכת.")

            # Navigate by Mishna Number
            elif action == 'navigate_by_number':
                mishna_number = request.form.get('mishna_number')
                current_app.logger.info(f'Navigating to mishna number: {mishna_number}')
                
                if mishna_number and mishna_number.isdigit():
                    number = int(mishna_number)
                    # Validate number is in valid range
                    if 1 <= number <= 108:
                        result = Mishna.query.filter_by(number=number).first()
                        results = [result] if result else []
                        current_app.logger.info(f'Found mishna with number {number}: {bool(result)}')
                    else:
                        current_app.logger.warning(f'Invalid mishna number: {number}')
                        results = []
                else:
                    current_app.logger.warning(f'Invalid mishna number format: {mishna_number}')
                    results = []

            # ============================================================================
            # AI/Semantic Search - COMMENTED OUT (not in use)
            # ============================================================================
            # This search functionality has been disabled to reduce memory usage.
            # The route handler remains here but will not be called since the UI
            # button has been removed from index.html
            # ============================================================================
            
            # # Semantic AI Search
            # elif action == 'search_semantic':
            #     query_text = request.form.get('semantic_query', '').strip()
            #     current_app.logger.info(f'Performing semantic search with query length: {len(query_text)} characters')
            #     
            #     # Additional rate limiting for expensive semantic search
            #     from utils.rate_limiter import rate_limiter
            #     from utils.search_cache import search_cache
            #     
            #     key = request.remote_addr or 'unknown'
            #     if not rate_limiter.is_allowed(key + '_semantic', 10, 60):
            #         current_app.logger.warning(f'Semantic search rate limit exceeded for {key}')
            #         return render_template('error.html', 
            #                              error="חרגת ממגבלת החיפוש הסמנטי. מותרות 10 בקשות בדקה. אנא נסה שוב בעוד מספר שניות.")
            #     
            #     # Check cache first
            #     cached_results = search_cache.get(query_text)
            #     if cached_results is not None:
            #         current_app.logger.info(f'Cache hit for query: {query_text[:50]}...')
            #         results, compromise_info = cached_results
            #     else:
            #         current_app.logger.info(f'Cache miss - performing semantic search')
            #         # Lazy-load the model only when needed
            #         engine = get_semantic_search_engine()
            #         results, compromise_info = engine.search_with_compromise(query_text)
            #         # Cache the results
            #         search_cache.set(query_text, (results, compromise_info))
            #     
            #     # Log compromise mode status
            #     if compromise_info['is_active']:
            #         current_app.logger.info(
            #             f'Compromise mode was activated: '
            #             f'Found results at {compromise_info["current_threshold"]}% '
            #             f'(initial: {compromise_info["initial_threshold"]}%, '
            #             f'attempts: {compromise_info["attempts"]})'
            #         )

        # Capture search query for display
        search_query = None
        aws_semantic_query = None
        is_semantic_search = False
        is_exact_match = False
        
        if request.method == 'POST':
            if action == 'search_free_text':
                search_query = mishna_form.text.data
            elif action == 'search_aws_semantic':
                aws_semantic_query = request.form.get('aws_semantic_query', '').strip()
                search_query = aws_semantic_query
                is_semantic_search = True
            elif action == 'search_smart':
                search_query = request.form.get('search_query', '').strip()
                is_exact_match = request.form.get('exact_match') == 'on'
                is_semantic_search = not is_exact_match  # It's semantic if not exact match
            # elif action == 'search_semantic':  # COMMENTED OUT - AI search disabled
            #     search_query = request.form.get('semantic_query', '').strip()
            #     is_semantic_search = True

        return render_template('index.html',
                               form=mishna_form,
                               results=results,
                               searchType=search_type,
                               search_query=search_query,
                               aws_semantic_query=aws_semantic_query,
                               is_semantic_search=is_semantic_search,
                               is_exact_match=is_exact_match,
                               ALLOWED_CHAPTERS=ALLOWED_CHAPTERS,
                               all_tags=tags_with_categories,
                               categories=categories_serialized,
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
        
        # Get all categories and tags
        categories = Category.query.all()
        uncategorized_tags = Tag.query.filter_by(category_id=None).all()
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

            # Handle Categories
            elif action == "add_category":
                new_category_name = tag_form.new_category_name.data
                new_category_color = tag_form.new_category_color.data
                current_app.logger.info(f'Attempting to add new category: {new_category_name} with color: {new_category_color}')

                if new_category_name:
                    existing_category = Category.query.filter_by(name=new_category_name).first()
                    if not existing_category:
                        try:
                            # Use the color from the form, or default if not provided
                            category_color = new_category_color if new_category_color else '#F5F5F5'
                            
                            new_category = Category(name=new_category_name, color=category_color)
                            db.session.add(new_category)
                            db.session.commit()
                            tag_message = "הקטגוריה הוספה בהצלחה!"
                            current_app.logger.info(f'Successfully added new category: {new_category_name} with color: {category_color}')
                        except SQLAlchemyError as e:
                            db.session.rollback()
                            current_app.logger.error(f'Database error while adding category: {str(e)}', exc_info=True)
                            tag_message = "אירעה שגיאה בהוספת הקטגוריה"
                    else:
                        current_app.logger.info(f'Category already exists: {new_category_name}')
                        tag_message = "הקטגוריה כבר קיימת."

            # Handle Tags
            elif action == "add_tag":
                new_tag_name = tag_form.name.data
                category_id = tag_form.category_id.data
                current_app.logger.info(f'Attempting to add new tag: {new_tag_name}')

                if new_tag_name:
                    existing_tag = Tag.query.filter_by(name=new_tag_name).first()
                    if not existing_tag:
                        try:
                            new_tag = Tag(
                                name=new_tag_name,
                                category_id=category_id if category_id != 0 else None
                            )
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

            # Handle Tag Editing
            elif action == "edit_tag":
                tag_id = request.form.get('tag_to_edit')
                new_category_id = request.form.get('new_category_id')
                current_app.logger.info(f'Attempting to edit tag ID: {tag_id}')

                if tag_id:
                    try:
                        tag = Tag.query.get(tag_id)
                        if tag:
                            # Convert '0' to None for uncategorized tags
                            tag.category_id = None if new_category_id == '0' else int(new_category_id)
                            db.session.commit()
                            tag_message = "קטגורית הנושא עודכנה בהצלחה!"
                            current_app.logger.info(f'Successfully updated tag ID: {tag_id}')
                        else:
                            current_app.logger.warning(f'Tag not found for editing: {tag_id}')
                            tag_message = "לא הצלחנו למצוא את הנושא במאגר."
                    except SQLAlchemyError as e:
                        db.session.rollback()
                        current_app.logger.error(f'Database error while editing tag: {str(e)}', exc_info=True)
                        tag_message = "אירעה שגיאה בעדכון הנושא"
                else:
                    current_app.logger.warning('No tag ID provided for editing')
                    tag_message = "בחר נושא לעריכה."

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
                               categories=categories,
                               uncategorized_tags=uncategorized_tags,
                               selected_tags=selected_tags,
                               selected_chapter=mishna_form.chapter.data,
                               selected_mishna=mishna_form.mishna.data)

    except Exception as e:
        current_app.logger.error(f'Unexpected error in manage_content: {str(e)}', exc_info=True)
        return render_template('error.html', error="An error occurred while managing content")
