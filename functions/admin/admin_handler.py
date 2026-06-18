"""Admin handler Lambda function for Pirkei Avot Finder.

Routes all authenticated admin endpoints: Mishna CRUD, Tag CRUD,
Category creation, user management, and AI search log retrieval.
JWT validation is handled by the API Gateway Cognito authorizer
before this handler is invoked.
"""

import json
import logging
import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.exc import SQLAlchemyError

from db import Session
from models import Mishna, Tag, Category, mishna_tag, UserFavorite, UserLearned, AiSearchLog
from text_utils import remove_niqqud
from response import success_response, error_response, serialize_mishna, serialize_search_log

logger = logging.getLogger()
logger.setLevel(logging.INFO)

COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')
CACHE_GENERATOR_FUNCTION_NAME = os.environ.get('CACHE_GENERATOR_FUNCTION_NAME', '')
cognito_client = boto3.client('cognito-idp')
lambda_client = boto3.client('lambda')


def _get_caller_role(event):
    """Extract the custom:role claim from the JWT claims injected by API Gateway."""
    claims = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
    )
    return claims.get('custom:role', 'user')


def _require_admin(event):
    """Return a 403 error response if the caller is not an admin, else None."""
    if _get_caller_role(event) != 'admin':
        return error_response('אין לך הרשאה לבצע פעולה זו', 'FORBIDDEN', 403)
    return None


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

        # GET /api/admin/users/search
        elif path == '/api/admin/users/search' and method == 'GET':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            return _search_users(event)

        # GET /api/admin/users
        elif path == '/api/admin/users' and method == 'GET':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            return _list_users(event)

        # POST /api/admin/users/{email}/disable
        elif path.startswith('/api/admin/users/') and '/disable' in path and method == 'POST':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            email = path.replace('/api/admin/users/', '').replace('/disable', '')
            return _disable_user(event, email)

        # POST /api/admin/users/{email}/enable
        elif path.startswith('/api/admin/users/') and '/enable' in path and method == 'POST':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            email = path.replace('/api/admin/users/', '').replace('/enable', '')
            return _enable_user(event, email)

        # DELETE /api/admin/users/{email}
        elif path.startswith('/api/admin/users/') and method == 'DELETE':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            email = path.replace('/api/admin/users/', '')
            return _delete_user(session, event, email)

        # GET /api/admin/search-logs/{log_id}/results
        elif path.startswith('/api/admin/search-logs/') and path.endswith('/results') and method == 'GET':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            log_id_str = path.replace('/api/admin/search-logs/', '').replace('/results', '')
            return _get_search_log_results(session, log_id_str)

        # GET /api/admin/search-logs
        elif path == '/api/admin/search-logs' and method == 'GET':
            auth_error = _require_admin(event)
            if auth_error:
                return auth_error
            return _get_search_logs(session, event)

        # POST /api/admin/generate-cache
        elif path == '/api/admin/generate-cache' and method == 'POST':
            return _generate_cache(event)

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
    pirush_url = (body.get('pirush_url') or '').strip() or None
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

    color = (body.get('color') or '').strip() or '#F5F5F5'

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


# ---------------------------------------------------------------------------
# User management helpers
# ---------------------------------------------------------------------------

def _get_user_attr(user, attr_name, default=''):
    """Extract a named attribute from a Cognito user's Attributes list."""
    for attr in user.get('Attributes', []):
        if attr['Name'] == attr_name:
            return attr['Value']
    return default


# ---------------------------------------------------------------------------
# User management endpoints  (GET /api/admin/users, etc.)
# ---------------------------------------------------------------------------

def _list_users(event):
    """Return a paginated list of all Cognito users.

    Supports optional pagination via next_token query param.
    Requirements: 10.2
    """
    params = event.get('queryStringParameters') or {}
    next_token = params.get('next_token')

    logger.info('Listing Cognito users')

    kwargs = {'UserPoolId': COGNITO_USER_POOL_ID, 'Limit': 20}
    if next_token:
        kwargs['PaginationToken'] = next_token

    response = cognito_client.list_users(**kwargs)

    users = [
        {
            'email': _get_user_attr(u, 'email'),
            'status': u['UserStatus'],
            'enabled': u['Enabled'],
            'created': u['UserCreateDate'].isoformat(),
            'role': _get_user_attr(u, 'custom:role', 'user'),
        }
        for u in response.get('Users', [])
    ]

    logger.info(f'Found {len(users)} users')
    return success_response({'users': users, 'next_token': response.get('PaginationToken')})


def _search_users(event):
    """Search Cognito users by email address.

    Requirements: 10.3
    """
    params = event.get('queryStringParameters') or {}
    email = params.get('email', '')

    logger.info(f'Searching Cognito users by email: {email}')

    response = cognito_client.list_users(
        UserPoolId=COGNITO_USER_POOL_ID,
        Filter=f'email = "{email}"',
        Limit=20,
    )

    users = [
        {
            'email': _get_user_attr(u, 'email'),
            'status': u['UserStatus'],
            'enabled': u['Enabled'],
            'created': u['UserCreateDate'].isoformat(),
            'role': _get_user_attr(u, 'custom:role', 'user'),
        }
        for u in response.get('Users', [])
    ]

    logger.info(f'Search returned {len(users)} users')
    return success_response({'users': users})


def _disable_user(event, email):
    """Disable a Cognito user account.

    Prevents an admin from disabling their own account.
    Requirements: 10.4, 10.7
    """
    caller_email = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
             .get('email', '')
    )

    if caller_email == email:
        return error_response('לא ניתן לבצע פעולה זו על החשבון שלך', 'VALIDATION_ERROR', 400)

    logger.info(f'Disabling user: {email}')

    try:
        cognito_client.admin_disable_user(UserPoolId=COGNITO_USER_POOL_ID, Username=email)
    except cognito_client.exceptions.UserNotFoundException:
        return error_response('המשתמש לא נמצא', 'NOT_FOUND', 404)

    logger.info(f'User disabled: {email}')
    return success_response({'message': 'המשתמש הושבת בהצלחה'})


def _enable_user(event, email):
    """Enable a previously disabled Cognito user account.

    Requirements: 10.5
    """
    logger.info(f'Enabling user: {email}')

    try:
        cognito_client.admin_enable_user(UserPoolId=COGNITO_USER_POOL_ID, Username=email)
    except cognito_client.exceptions.UserNotFoundException:
        return error_response('המשתמש לא נמצא', 'NOT_FOUND', 404)

    logger.info(f'User enabled: {email}')
    return success_response({'message': 'המשתמש הופעל בהצלחה'})


def _delete_user(session, event, email):
    """Delete a Cognito user and cascade-delete their favorites from the DB.

    Prevents an admin from deleting their own account.
    Requirements: 10.6, 10.7
    """
    caller_email = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
             .get('email', '')
    )

    if caller_email == email:
        return error_response('לא ניתן לבצע פעולה זו על החשבון שלך', 'VALIDATION_ERROR', 400)

    logger.info(f'Deleting user: {email}')

    # Fetch the user's sub from Cognito to identify their DB records
    try:
        user_data = cognito_client.admin_get_user(UserPoolId=COGNITO_USER_POOL_ID, Username=email)
    except cognito_client.exceptions.UserNotFoundException:
        return error_response('המשתמש לא נמצא', 'NOT_FOUND', 404)

    user_sub = None
    for attr in user_data.get('UserAttributes', []):
        if attr['Name'] == 'sub':
            user_sub = attr['Value']
            break

    # Delete all favorites and learned records for this user from the database
    if user_sub:
        deleted_count = session.query(UserFavorite).filter_by(user_sub=user_sub).delete()
        deleted_learned_count = session.query(UserLearned).filter_by(user_sub=user_sub).delete()
        logger.info(f'Deleted {deleted_count} favorites and {deleted_learned_count} learned records for user sub: {user_sub}')

    # Delete the Cognito user
    cognito_client.admin_delete_user(UserPoolId=COGNITO_USER_POOL_ID, Username=email)
    session.commit()

    logger.info(f'User deleted: {email}')
    return success_response({'message': 'המשתמש נמחק בהצלחה'})


# ---------------------------------------------------------------------------
# Cache generation  (POST /api/admin/generate-cache)
# ---------------------------------------------------------------------------

def _generate_cache(event):
    """Invoke the Cache Generator Lambda and return its response."""
    auth_error = _require_admin(event)
    if auth_error:
        return auth_error

    logger.info('Invoking Cache Generator Lambda')

    try:
        response = lambda_client.invoke(
            FunctionName=CACHE_GENERATOR_FUNCTION_NAME,
            InvocationType='RequestResponse',
        )

        # Check for Lambda-level errors
        if response.get('FunctionError'):
            error_payload = response['Payload'].read().decode('utf-8')
            logger.error(f'Cache Generator Lambda error: {error_payload}')
            return error_response('שגיאה בהפעלת מחולל המטמון', 'INTERNAL_ERROR', 500)

        # Parse and forward the Cache Generator's response
        payload = json.loads(response['Payload'].read().decode('utf-8'))
        return payload

    except ClientError as e:
        logger.error(f'Error invoking Cache Generator Lambda: {str(e)}', exc_info=True)
        return error_response('שגיאה בהפעלת מחולל המטמון', 'INTERNAL_ERROR', 500)


# ---------------------------------------------------------------------------
# AI search logs endpoints
# (GET /api/admin/search-logs, GET /api/admin/search-logs/{id}/results)
# ---------------------------------------------------------------------------

def _get_search_log_results(session, log_id_str):
    """Return the Mishna objects referenced by a search log entry's result_ids.

    Parses the comma-separated result_ids field, queries the mishna table,
    and returns the list of Mishna objects with their text.
    """
    try:
        log_id = int(log_id_str)
    except (ValueError, TypeError):
        return error_response('מזהה לוג לא חוקי', 'VALIDATION_ERROR', 400)

    log_entry = session.query(AiSearchLog).filter_by(id=log_id).first()
    if not log_entry:
        return error_response('רשומת לוג לא נמצאה', 'NOT_FOUND', 404)

    # Parse result_ids — may be NULL or empty
    result_ids_str = (log_entry.result_ids or '').strip()
    if not result_ids_str:
        return success_response({
            'query_text': log_entry.query_text,
            'results': []
        })

    mishna_ids = [mid.strip() for mid in result_ids_str.split(',') if mid.strip()]

    # Query all matching Mishna records in one query
    mishnas = session.query(Mishna).filter(Mishna.id.in_(mishna_ids)).all()

    # Preserve the original order from result_ids
    mishna_map = {m.id: m for m in mishnas}
    ordered_results = []
    for mid in mishna_ids:
        if mid in mishna_map:
            m = mishna_map[mid]
            ordered_results.append({
                'id': m.id,
                'chapter': m.chapter,
                'mishna': m.mishna,
                'text_pretty': m.text_pretty,
            })

    return success_response({
        'query_text': log_entry.query_text,
        'results': ordered_results,
    })


def _get_search_logs(session, event):
    """Return paginated AI search logs with optional filters.

    Supports filtering by date_from, date_to, and query substring.
    Requirements: 7.4, 7.5, 10.9
    """
    params = event.get('queryStringParameters') or {}

    date_from = params.get('date_from')
    date_to = params.get('date_to')
    query_filter = params.get('query')

    try:
        page = int(params.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = int(params.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20

    logger.info(f'Fetching search logs — page: {page}, page_size: {page_size}, '
                f'date_from: {date_from}, date_to: {date_to}, query: {query_filter}')

    q = session.query(AiSearchLog).order_by(AiSearchLog.created_at.desc())

    if date_from:
        q = q.filter(AiSearchLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(AiSearchLog.created_at <= datetime.fromisoformat(date_to))
    if query_filter:
        q = q.filter(AiSearchLog.query_text.ilike(f'%{query_filter}%'))

    total = q.count()
    logs = q.offset((page - 1) * page_size).limit(page_size).all()

    serialized = [serialize_search_log(log) for log in logs]

    logger.info(f'Returning {len(serialized)} of {total} search logs')
    return success_response({
        'logs': serialized,
        'total': total,
        'page': page,
        'page_size': page_size,
    })
