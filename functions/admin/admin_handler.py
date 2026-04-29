"""Admin handler Lambda function for Pirkei Avot Finder.

Routes all authenticated admin endpoints: Mishna CRUD, Tag CRUD,
and Category creation. JWT validation is handled by the API Gateway
Cognito authorizer before this handler is invoked.
"""

import json
import logging

from sqlalchemy.exc import SQLAlchemyError

from db import Session
from models import Mishna, Tag, Category, mishna_tag
from text_utils import remove_niqqud
from response import success_response, error_response, serialize_mishna

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct admin function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'Admin handler invoked: {method} {path}')

    session = Session()
    try:
        # POST /api/admin/mishna
        if path == '/api/admin/mishna' and method == 'POST':
            return _create_or_update_mishna(session, event)

        # GET /api/admin/mishna/{id}
        elif path.startswith('/api/admin/mishna/') and method == 'GET':
            mishna_id = path.replace('/api/admin/mishna/', '')
            return _get_mishna(session, mishna_id)

        # GET /api/admin/tags
        elif path == '/api/admin/tags' and method == 'GET':
            return _get_all_tags(session)

        # POST /api/admin/tag
        elif path == '/api/admin/tag' and method == 'POST':
            return _create_tag(session, event)

        # PUT /api/admin/tag/{id}
        elif path.startswith('/api/admin/tag/') and method == 'PUT':
            tag_id_str = path.replace('/api/admin/tag/', '')
            return _update_tag(session, event, tag_id_str)

        # DELETE /api/admin/tag/{id}
        elif path.startswith('/api/admin/tag/') and method == 'DELETE':
            tag_id_str = path.replace('/api/admin/tag/', '')
            return _delete_tag(session, tag_id_str)

        # POST /api/admin/category
        elif path == '/api/admin/category' and method == 'POST':
            return _create_category(session, event)

        else:
            return error_response('הנתיב המבוקש לא נמצא', 'NOT_FOUND', 404)

    except SQLAlchemyError as e:
        logger.error(f'Database error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בגישה למסד הנתונים', 'INTERNAL_ERROR', 500)
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה פנימית', 'INTERNAL_ERROR', 500)
    finally:
        session.close()


def _parse_body(event):
    """Parse JSON body from the event, handling both string and dict formats."""
    body = event.get('body', '{}')
    if isinstance(body, str):
        return json.loads(body)
    return body


# ---------------------------------------------------------------------------
# Mishna CRUD  (GET /api/admin/mishna/{id}, POST /api/admin/mishna)
# ---------------------------------------------------------------------------

def _get_mishna(session, mishna_id):
    """Return an existing Mishna with its tags, or 404."""
    logger.info(f'Get mishna — id: {mishna_id}')

    mishna = session.query(Mishna).filter_by(id=mishna_id).first()

    if not mishna:
        return error_response('משנה לא נמצאה', 'NOT_FOUND', 404)

    logger.info(f'Found mishna: {mishna.id}')
    return success_response(serialize_mishna(mishna))


def _create_or_update_mishna(session, event):
    """Create or update a Mishna record.

    Auto-generates composite id as {chapter}_{mishna} and text_raw
    via remove_niqqud(text_pretty). Associates tags and sets optional pirush_url.
    """
    body = _parse_body(event)

    chapter = body.get('chapter', '').strip()
    mishna = body.get('mishna', '').strip()
    text_pretty = body.get('text_pretty', '').strip()

    if not chapter or not mishna or not text_pretty:
        return error_response('חסרים שדות חובה: chapter, mishna, text_pretty', 'VALIDATION_ERROR', 400)

    # Auto-generate derived fields
    composite_id = f'{chapter}_{mishna}'
    text_raw = remove_niqqud(text_pretty)
    pirush_url = body.get('pirush_url', '').strip() or None
    tag_ids = body.get('tags', [])

    logger.info(f'Create/update mishna — id: {composite_id}, tags: {tag_ids}')

    try:
        # Fetch associated tags
        new_tags = session.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

        existing = session.query(Mishna).filter_by(id=composite_id).first()

        if existing:
            # Update existing record
            existing.text_pretty = text_pretty
            existing.text_raw = text_raw
            existing.tags = new_tags
            existing.pirush_url = pirush_url
            session.commit()
            logger.info(f'Updated mishna: {composite_id}')
            return success_response({
                'message': 'המשנה עודכנה בהצלחה',
                'mishna': serialize_mishna(existing)
            })
        else:
            # Create new record — number must be provided by the client
            number = body.get('number')
            if number is None:
                return error_response('חסר שדה number למשנה חדשה', 'VALIDATION_ERROR', 400)

            new_mishna = Mishna(
                chapter=chapter,
                mishna=mishna,
                number=int(number),
                text_pretty=text_pretty,
                text_raw=text_raw,
                tags=new_tags,
                interpretation=body.get('interpretation', ''),
                pirush_url=pirush_url,
            )
            session.add(new_mishna)
            session.commit()
            logger.info(f'Created mishna: {composite_id}')
            return success_response({
                'message': 'המשנה נוספה בהצלחה',
                'mishna': serialize_mishna(new_mishna)
            }, status=201)

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while saving mishna: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בשמירת המשנה', 'INTERNAL_ERROR', 500)


# ---------------------------------------------------------------------------
# Get all tags grouped by category  (GET /api/admin/tags)
# ---------------------------------------------------------------------------

def _get_all_tags(session):
    """Return all tags grouped by category for the admin panel."""
    logger.info('Fetching all tags for admin panel')

    categories_list = session.query(Category).all()
    tags = session.query(Tag).all()

    # Build category map
    cat_data = []
    cat_tags_map = {cat.id: [] for cat in categories_list}
    uncategorized = []

    for tag in tags:
        tag_dict = {'id': tag.id, 'name': tag.name, 'category_id': tag.category_id}
        if tag.category_id and tag.category_id in cat_tags_map:
            cat_tags_map[tag.category_id].append(tag_dict)
        else:
            uncategorized.append(tag_dict)

    for cat in categories_list:
        cat_data.append({
            'id': cat.id,
            'name': cat.name,
            'color': cat.color,
            'tags': cat_tags_map.get(cat.id, []),
        })

    logger.info(f'Found {len(tags)} tags in {len(categories_list)} categories')
    return success_response({
        'categories': cat_data,
        'uncategorized_tags': uncategorized,
    })


# ---------------------------------------------------------------------------
# Tag CRUD  (POST /api/admin/tag, PUT /api/admin/tag/{id}, DELETE /api/admin/tag/{id})
# ---------------------------------------------------------------------------

def _create_tag(session, event):
    """Create a new tag with name and optional category_id. Returns 409 if name exists."""
    body = _parse_body(event)

    name = body.get('name', '').strip()
    if not name:
        return error_response('חסר שם תגית', 'VALIDATION_ERROR', 400)

    category_id = body.get('category_id')
    # Treat 0 or empty as uncategorized
    if not category_id or category_id == 0:
        category_id = None

    logger.info(f'Create tag — name: {name}, category_id: {category_id}')

    # Check for duplicate name
    existing = session.query(Tag).filter_by(name=name).first()
    if existing:
        return error_response('התגית כבר קיימת', 'DUPLICATE_ENTRY', 409)

    try:
        new_tag = Tag(name=name, category_id=category_id)
        session.add(new_tag)
        session.commit()
        logger.info(f'Created tag: {new_tag.id} — {name}')
        return success_response({
            'message': 'התגית נוספה בהצלחה',
            'tag': {
                'id': new_tag.id,
                'name': new_tag.name,
                'category_id': new_tag.category_id,
            }
        }, status=201)

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while creating tag: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בהוספת התגית', 'INTERNAL_ERROR', 500)


def _update_tag(session, event, tag_id_str):
    """Update tag name and/or category_id. Returns 409 if new name conflicts."""
    try:
        tag_id = int(tag_id_str)
    except (ValueError, TypeError):
        return error_response('מזהה תגית לא חוקי', 'VALIDATION_ERROR', 400)

    body = _parse_body(event)
    new_name = body.get('name', '').strip() if body.get('name') else None
    new_category_id = body.get('category_id')

    logger.info(f'Update tag — id: {tag_id}, new_name: {new_name}, new_category_id: {new_category_id}')

    tag = session.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        return error_response('תגית לא נמצאה', 'NOT_FOUND', 404)

    try:
        # Check name conflict if name is being changed
        if new_name and new_name != tag.name:
            conflict = session.query(Tag).filter_by(name=new_name).first()
            if conflict and conflict.id != tag_id:
                return error_response('שם הנושא כבר קיים במערכת', 'DUPLICATE_ENTRY', 409)
            tag.name = new_name

        # Update category — treat 0 as uncategorized
        if new_category_id is not None:
            tag.category_id = None if new_category_id == 0 else int(new_category_id)

        session.commit()
        logger.info(f'Updated tag: {tag_id}')
        return success_response({
            'message': 'הנושא עודכן בהצלחה',
            'tag': {
                'id': tag.id,
                'name': tag.name,
                'category_id': tag.category_id,
            }
        })

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while updating tag: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בעדכון הנושא', 'INTERNAL_ERROR', 500)


def _delete_tag(session, tag_id_str):
    """Delete a tag and its mishna_tag associations."""
    try:
        tag_id = int(tag_id_str)
    except (ValueError, TypeError):
        return error_response('מזהה תגית לא חוקי', 'VALIDATION_ERROR', 400)

    logger.info(f'Delete tag — id: {tag_id}')

    tag = session.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        return error_response('תגית לא נמצאה', 'NOT_FOUND', 404)

    try:
        # Remove mishna_tag associations explicitly, then delete the tag
        session.execute(mishna_tag.delete().where(mishna_tag.c.tag_id == tag_id))
        session.delete(tag)
        session.commit()
        logger.info(f'Deleted tag: {tag_id}')
        return success_response({'message': 'התגית נמחקה בהצלחה'})

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while deleting tag: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה במחיקת התגית', 'INTERNAL_ERROR', 500)


# ---------------------------------------------------------------------------
# Category creation  (POST /api/admin/category)
# ---------------------------------------------------------------------------

def _create_category(session, event):
    """Create a new category with name and optional color (default #F5F5F5).
    Returns 409 if category name already exists.
    """
    body = _parse_body(event)

    name = body.get('name', '').strip()
    if not name:
        return error_response('חסר שם קטגוריה', 'VALIDATION_ERROR', 400)

    color = body.get('color', '').strip() or '#F5F5F5'

    logger.info(f'Create category — name: {name}, color: {color}')

    # Check for duplicate name
    existing = session.query(Category).filter_by(name=name).first()
    if existing:
        return error_response('הקטגוריה כבר קיימת', 'DUPLICATE_ENTRY', 409)

    try:
        new_category = Category(name=name, color=color)
        session.add(new_category)
        session.commit()
        logger.info(f'Created category: {new_category.id} — {name}')
        return success_response({
            'message': 'הקטגוריה נוספה בהצלחה',
            'category': {
                'id': new_category.id,
                'name': new_category.name,
                'color': new_category.color,
            }
        }, status=201)

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while creating category: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בהוספת הקטגוריה', 'INTERNAL_ERROR', 500)
