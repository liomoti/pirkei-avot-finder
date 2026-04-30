"""User handler Lambda function for Pirkei Avot Finder.

Routes all authenticated user endpoints: favorites CRUD and profile retrieval.
JWT validation is handled by the API Gateway Cognito authorizer before this
handler is invoked. The user's Cognito sub is extracted from the JWT claims.
"""

import json
import logging

from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import Session
from models import Mishna, UserFavorite
from response import success_response, error_response, serialize_favorite

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct user function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'User handler invoked: {method} {path}')

    # Extract user sub from JWT claims (injected by API Gateway Cognito authorizer)
    user_sub = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
             .get('sub', '')
    )

    session = Session()
    try:
        # GET /api/user/favorites
        if path == '/api/user/favorites' and method == 'GET':
            return _get_favorites(session, user_sub)

        # POST /api/user/favorites
        elif path == '/api/user/favorites' and method == 'POST':
            return _add_favorite(session, event, user_sub)

        # DELETE /api/user/favorites/{mishna_id}
        elif path.startswith('/api/user/favorites/') and method == 'DELETE':
            mishna_id = path.replace('/api/user/favorites/', '')
            return _remove_favorite(session, user_sub, mishna_id)

        # GET /api/user/profile
        elif path == '/api/user/profile' and method == 'GET':
            return _get_profile(event)

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
# Favorites  (GET, POST, DELETE /api/user/favorites)
# ---------------------------------------------------------------------------

def _get_favorites(session, user_sub):
    """Return all favorites for the user, ordered by created_at DESC.

    Validates: Requirements 6.1, 6.3
    """
    logger.info(f'Get favorites — user_sub: {user_sub}')

    favorites = (
        session.query(UserFavorite)
               .filter_by(user_sub=user_sub)
               .order_by(UserFavorite.created_at.desc())
               .all()
    )

    serialized = [serialize_favorite(f) for f in favorites]
    logger.info(f'Found {len(serialized)} favorites for user')

    return success_response({'favorites': serialized, 'count': len(serialized)})


def _add_favorite(session, event, user_sub):
    """Add a Mishna to the user's favorites.

    Validates: Requirements 6.2, 6.6
    """
    body = _parse_body(event)
    mishna_id = body.get('mishna_id', '').strip()

    if not mishna_id:
        return error_response('חסר מזהה משנה', 'VALIDATION_ERROR', 400)

    logger.info(f'Add favorite — user_sub: {user_sub}, mishna_id: {mishna_id}')

    # Verify the Mishna exists
    mishna = session.query(Mishna).filter_by(id=mishna_id).first()
    if not mishna:
        return error_response('המשנה לא נמצאה', 'NOT_FOUND', 404)

    try:
        favorite = UserFavorite(user_sub=user_sub, mishna_id=mishna_id)
        session.add(favorite)
        session.commit()
        logger.info(f'Added favorite: user_sub={user_sub}, mishna_id={mishna_id}')
        return success_response(
            {'message': 'המשנה נוספה למועדפים', 'mishna_id': mishna_id},
            status=201
        )

    except IntegrityError:
        session.rollback()
        logger.warning(f'Duplicate favorite attempt: user_sub={user_sub}, mishna_id={mishna_id}')
        return error_response('המשנה כבר נמצאת במועדפים', 'DUPLICATE_ENTRY', 409)


def _remove_favorite(session, user_sub, mishna_id):
    """Remove a Mishna from the user's favorites.

    Validates: Requirements 6.3
    """
    logger.info(f'Remove favorite — user_sub: {user_sub}, mishna_id: {mishna_id}')

    favorite = (
        session.query(UserFavorite)
               .filter_by(user_sub=user_sub, mishna_id=mishna_id)
               .first()
    )

    if not favorite:
        return error_response('המשנה לא נמצאה במועדפים', 'NOT_FOUND', 404)

    session.delete(favorite)
    session.commit()
    logger.info(f'Removed favorite: user_sub={user_sub}, mishna_id={mishna_id}')

    return success_response({'message': 'המשנה הוסרה מהמועדפים'})


# ---------------------------------------------------------------------------
# Profile  (GET /api/user/profile)
# ---------------------------------------------------------------------------

def _get_profile(event):
    """Return the authenticated user's email and role from JWT claims.

    Validates: Requirements 8.1
    """
    claims = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
    )

    email = claims.get('email', '')
    role = claims.get('custom:role', 'user')

    logger.info(f'Get profile — email: {email}, role: {role}')

    return success_response({'email': email, 'role': role})
