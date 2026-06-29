"""User handler Lambda function for Pirkei Avot Finder.

Routes all authenticated user endpoints: favorites CRUD and profile retrieval/update.
JWT validation is handled by the API Gateway Cognito authorizer before this
handler is invoked. The user's Cognito sub and email are extracted from JWT claims.
Profile updates (full_name) are written directly to Cognito via AdminUpdateUserAttributes.
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import Session
from models import Mishna, UserFavorite, UserLearned
from constants import ALLOWED_CHAPTERS
from response import success_response, error_response, serialize_favorite

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito client initialized at module level — persists across warm invocations
cognito_client = boto3.client('cognito-idp')
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct user function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'User handler invoked: {method} {path}')

    # Extract claims injected by API Gateway Cognito authorizer
    claims = (
        event.get('requestContext', {})
             .get('authorizer', {})
             .get('jwt', {})
             .get('claims', {})
    )
    user_sub = claims.get('sub', '')

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

        # GET /api/user/learned
        elif path == '/api/user/learned' and method == 'GET':
            return _get_learned(session, user_sub)

        # POST /api/user/learned
        elif path == '/api/user/learned' and method == 'POST':
            return _add_learned(session, event, user_sub)

        # DELETE /api/user/learned/{mishna_id}
        elif path.startswith('/api/user/learned/') and method == 'DELETE':
            mishna_id = path.replace('/api/user/learned/', '')
            return _remove_learned(session, user_sub, mishna_id)

        # GET /api/user/progress
        elif path == '/api/user/progress' and method == 'GET':
            return _get_progress(session, user_sub)

        # GET /api/user/profile
        elif path == '/api/user/profile' and method == 'GET':
            return _get_profile(claims)

        # PUT /api/user/profile
        elif path == '/api/user/profile' and method == 'PUT':
            return _update_profile(event, claims)

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
    return body or {}


# ---------------------------------------------------------------------------
# Favorites  (GET, POST, DELETE /api/user/favorites)
# ---------------------------------------------------------------------------

def _get_favorites(session, user_sub):
    """Return all favorites for the user, ordered by created_at DESC."""
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
    """Add a Mishna to the user's favorites."""
    body = _parse_body(event)
    mishna_id = body.get('mishna_id', '').strip()

    if not mishna_id:
        return error_response('חסר מזהה משנה', 'VALIDATION_ERROR', 400)

    logger.info(f'Add favorite — user_sub: {user_sub}, mishna_id: {mishna_id}')

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
    """Remove a Mishna from the user's favorites."""
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
# Profile  (GET, PUT /api/user/profile)
# ---------------------------------------------------------------------------

def _get_profile(claims):
    """Return the authenticated user's profile.

    email and role come from JWT claims (always fresh from Cognito authorizer).
    full_name is fetched live from Cognito via AdminGetUser so it reflects
    the latest value even if the stored JWT predates the last update.
    """
    email = claims.get('email', '')
    role = claims.get('custom:role', 'user')

    logger.info(f'Get profile — email: {email}, role: {role}')

    # Fetch full_name live from Cognito so it's always up-to-date
    full_name = ''
    if email and COGNITO_USER_POOL_ID:
        try:
            response = cognito_client.admin_get_user(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=email
            )
            attrs = {a['Name']: a['Value'] for a in response.get('UserAttributes', [])}
            full_name = attrs.get('custom:full_name', '')
        except ClientError as e:
            # Non-fatal — return empty string if lookup fails
            logger.warning(f'Could not fetch full_name from Cognito: {str(e)}')

    return success_response({'email': email, 'role': role, 'full_name': full_name})


def _update_profile(event, claims):
    """Update custom:full_name in Cognito via AdminUpdateUserAttributes.

    Uses the user's email (username) from JWT claims and the pool ID from env.
    No access token needed — Lambda has AdminUpdateUserAttributes IAM permission.
    """
    body = _parse_body(event)
    full_name = body.get('full_name', '').strip()

    if len(full_name) > 200:
        return error_response('השם המלא ארוך מדי (מקסימום 200 תווים)', 'VALIDATION_ERROR', 400)

    # Cognito username is the email (UsernameAttributes: [email])
    username = claims.get('email', '')
    if not username:
        return error_response('לא ניתן לזהות את המשתמש', 'AUTH_REQUIRED', 401)

    logger.info(f'Update profile — username: {username}, full_name: {full_name}')

    try:
        cognito_client.admin_update_user_attributes(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            UserAttributes=[
                {'Name': 'custom:full_name', 'Value': full_name}
            ]
        )
        logger.info(f'Updated custom:full_name for: {username}')
        return success_response({'message': 'הפרופיל עודכן בהצלחה', 'full_name': full_name})

    except ClientError as e:
        logger.error(f'Cognito error updating profile: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בעדכון הפרופיל', 'INTERNAL_ERROR', 500)


# ---------------------------------------------------------------------------
# Learned  (GET, POST, DELETE /api/user/learned and GET /api/user/progress)
# ---------------------------------------------------------------------------

def _get_learned(session, user_sub):
    """Return all learned mishna_id values for the user, ordered by created_at DESC."""
    logger.info(f'Get learned — user_sub: {user_sub}')

    learned_records = (
        session.query(UserLearned)
               .filter_by(user_sub=user_sub)
               .order_by(UserLearned.created_at.desc())
               .all()
    )

    mishna_ids = [r.mishna_id for r in learned_records]
    logger.info(f'Found {len(mishna_ids)} learned records for user')

    return success_response({'learned': mishna_ids, 'count': len(mishna_ids)})


def _add_learned(session, event, user_sub):
    """Mark a Mishna as learned."""
    body = _parse_body(event)
    mishna_id = body.get('mishna_id', '').strip()

    if not mishna_id:
        return error_response('חסר מזהה משנה', 'VALIDATION_ERROR', 400)

    logger.info(f'Add learned — user_sub: {user_sub}, mishna_id: {mishna_id}')

    mishna = session.query(Mishna).filter_by(id=mishna_id).first()
    if not mishna:
        return error_response('המשנה לא נמצאה', 'NOT_FOUND', 404)

    try:
        learned = UserLearned(user_sub=user_sub, mishna_id=mishna_id)
        session.add(learned)
        session.commit()
        logger.info(f'Added learned: user_sub={user_sub}, mishna_id={mishna_id}')
        return success_response(
            {'message': 'המשנה סומנה כנלמדה', 'mishna_id': mishna_id},
            status=201
        )

    except IntegrityError:
        session.rollback()
        logger.warning(f'Duplicate learned attempt: user_sub={user_sub}, mishna_id={mishna_id}')
        return error_response('המשנה כבר סומנה כנלמדה', 'DUPLICATE_ENTRY', 409)


def _remove_learned(session, user_sub, mishna_id):
    """Remove a learned record."""
    logger.info(f'Remove learned — user_sub: {user_sub}, mishna_id: {mishna_id}')

    learned = (
        session.query(UserLearned)
               .filter_by(user_sub=user_sub, mishna_id=mishna_id)
               .first()
    )

    if not learned:
        return error_response('המשנה לא נמצאה ברשימת הנלמדות', 'NOT_FOUND', 404)

    session.delete(learned)
    session.commit()
    logger.info(f'Removed learned: user_sub={user_sub}, mishna_id={mishna_id}')

    return success_response({'message': 'הסימון כנלמדה הוסר'})


def _get_progress(session, user_sub):
    """Calculate per-chapter learning progress using ALLOWED_CHAPTERS."""
    logger.info(f'Get progress — user_sub: {user_sub}')

    learned_records = (
        session.query(UserLearned)
               .filter_by(user_sub=user_sub)
               .all()
    )

    # Build a set of learned mishna_ids
    learned_ids = {r.mishna_id for r in learned_records}

    # Group learned IDs by chapter (mishna_id format: "chapter_mishna", e.g. "א_א")
    learned_by_chapter = {}
    for mishna_id in learned_ids:
        parts = mishna_id.split('_', 1)
        if parts:
            chapter = parts[0]
            if chapter not in learned_by_chapter:
                learned_by_chapter[chapter] = 0
            learned_by_chapter[chapter] += 1

    # Build per-chapter stats using ALLOWED_CHAPTERS as source of truth
    chapters = []
    total_mishnayot = 0
    total_learned = len(learned_ids)

    chapter_names = {'א': 'פרק א', 'ב': 'פרק ב', 'ג': 'פרק ג', 'ד': 'פרק ד', 'ה': 'פרק ה', 'ו': 'פרק ו'}

    for chapter, mishna_list in ALLOWED_CHAPTERS.items():
        chapter_total = len(mishna_list)
        chapter_learned = learned_by_chapter.get(chapter, 0)
        chapter_remaining = chapter_total - chapter_learned
        is_completed = chapter_remaining == 0
        total_mishnayot += chapter_total

        chapters.append({
            'chapter': chapter,
            'chapter_name': chapter_names.get(chapter, f'פרק {chapter}'),
            'total': chapter_total,
            'learned': chapter_learned,
            'remaining': chapter_remaining,
            'is_completed': is_completed,
        })

    logger.info(f'Progress: {total_learned}/{total_mishnayot} learned')

    return success_response({
        'total_learned': total_learned,
        'total_mishnayot': total_mishnayot,
        'chapters': chapters,
    })
