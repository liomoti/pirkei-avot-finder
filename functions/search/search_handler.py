"""Search handler Lambda function for Pirkei Avot Finder.

Routes all public search endpoints: chapter/mishna, smart search,
tag-based search, and navigate-by-number.
"""

import base64
import json
import logging
import os

import boto3
from sqlalchemy.exc import SQLAlchemyError

from db import Session
from models import Mishna, Tag, Category, AiSearchLog, get_semantic_search_method
from constants import ALLOWED_CHAPTERS
from text_utils import remove_niqqud
from response import success_response, error_response, serialize_mishna

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lambda client initialized at module level — persists across warm invocations
lambda_client = boto3.client('lambda')


def _extract_user_sub_from_event(event):
    """Best-effort extraction of the Cognito sub claim from the Authorization header.

    Returns the sub string if a valid Bearer JWT is present, or None otherwise.
    """
    try:
        auth_header = (
            event.get('headers', {}).get('authorization', '')
            or event.get('headers', {}).get('Authorization', '')
        )
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header[len('Bearer '):]
        # JWT is three base64url-encoded segments separated by '.'
        parts = token.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        # Fix base64 padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        decoded = base64.urlsafe_b64decode(payload_b64)
        claims = json.loads(decoded)
        return claims.get('sub')
    except Exception:
        return None


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct search function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    params = event.get('queryStringParameters') or {}

    logger.info(f'Search handler invoked: {method} {path}, params: {params}')

    session = Session()
    try:
        if path == '/api/search/mishna' and method == 'GET':
            return _search_mishna(session, params)

        elif path == '/api/search/smart' and method == 'GET':
            return _search_smart(session, params, event)

        elif path == '/api/search/tags' and method == 'GET':
            return _search_tags(session, params)

        elif path == '/api/search/tags/all' and method == 'GET':
            return _get_all_tags(session)

        elif path.startswith('/api/search/number/') and method == 'GET':
            # Extract the number from the path
            n_str = path.replace('/api/search/number/', '')
            return _search_by_number(session, n_str)

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


# ---------------------------------------------------------------------------
# Chapter-and-Mishna search  (GET /api/search/mishna)
# ---------------------------------------------------------------------------

def _search_mishna(session, params):
    """Search by chapter and optional mishna identifier."""
    chapter = params.get('chapter', '')
    mishna = params.get('mishna', '')

    if not chapter:
        return error_response('חסר פרמטר פרק', 'VALIDATION_ERROR', 400)

    # Validate chapter against allowed list
    if chapter not in ALLOWED_CHAPTERS:
        return error_response('פרק לא חוקי', 'VALIDATION_ERROR', 400)

    # Validate mishna value when not requesting all
    if mishna and mishna != 'all' and mishna not in ALLOWED_CHAPTERS[chapter]:
        return error_response('משנה לא חוקית עבור פרק זה', 'VALIDATION_ERROR', 400)

    logger.info(f'Chapter/mishna search — chapter: {chapter}, mishna: {mishna}')

    if mishna == 'all':
        results = (
            session.query(Mishna)
            .filter(Mishna.chapter == chapter)
            .order_by(Mishna.number)
            .all()
        )
    else:
        composite_id = f'{chapter}_{mishna}'
        results = (
            session.query(Mishna)
            .filter(Mishna.id == composite_id)
            .all()
        )

    logger.info(f'Found {len(results)} results')
    return success_response([serialize_mishna(m) for m in results])


# ---------------------------------------------------------------------------
# Smart search  (GET /api/search/smart)
# ---------------------------------------------------------------------------

def _search_smart(session, params, event):
    """Exact-match text search or semantic AI search."""
    query = params.get('q', '').strip()
    exact_match = params.get('exact_match', 'false').lower() == 'true'

    if not query:
        return error_response('חסר טקסט לחיפוש', 'VALIDATION_ERROR', 400)

    logger.info(f'Smart search — query length: {len(query)}, exact_match: {exact_match}')

    if exact_match:
        return _exact_text_search(session, query)
    else:
        return _semantic_search(session, query, event)


def _exact_text_search(session, query):
    """Normalize query and perform ILIKE search on text_raw."""
    normalized = remove_niqqud(query)
    logger.info(f'Exact match search, normalized length: {len(normalized)}')

    results = (
        session.query(Mishna)
        .filter(Mishna.text_raw.ilike(f'%{normalized}%'))
        .order_by(Mishna.number)
        .all()
    )

    logger.info(f'Found {len(results)} results')
    return success_response([serialize_mishna(m) for m in results])


def _semantic_search(session, query, event):
    """Invoke the Semantic Search Lambda directly and fetch matching records."""
    # Select the target Lambda based on the active semantic search method
    method = get_semantic_search_method(session)
    if method == 'json_context':
        function_name = os.environ.get('JSON_CONTEXT_SEARCH_FUNCTION_NAME', '')
    else:
        function_name = os.environ.get('SEMANTIC_SEARCH_FUNCTION_NAME', '')

    if not function_name:
        logger.error('SEMANTIC_SEARCH_FUNCTION_NAME env var not configured')
        return error_response(
            'חיפוש סמנטי אינו מוגדר כראוי. אנא פנה למנהל המערכת.',
            'SEARCH_FAILED', 502
        )

    try:
        # Invoke the semantic search Lambda directly
        invoke_response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({'query': query}),
        )

        payload = json.loads(invoke_response['Payload'].read())

        # Handle Lambda error responses
        if invoke_response.get('FunctionError'):
            logger.error(f'Semantic Lambda error: {payload}')
            return error_response(
                'חיפוש סמנטי נכשל. אנא נסה שוב מאוחר יותר.',
                'SEARCH_FAILED', 502
            )

        # Parse the response body (may be wrapped in API Gateway format)
        if isinstance(payload.get('body'), str):
            api_data = json.loads(payload['body'])
        else:
            api_data = payload

        api_results = api_data.get('results', {})

        if not api_results:
            logger.info('Semantic search returned no results')
            _log_ai_search(session, query, [], _extract_user_sub_from_event(event), search_method=method)
            return success_response([])

        # Build a mapping of mishna_number -> score
        number_score_map = {}
        for num_str, score in api_results.items():
            try:
                number_score_map[int(num_str)] = float(score)
            except (ValueError, TypeError):
                logger.warning(f'Invalid result entry: {num_str} -> {score}')
                continue

        # Fetch matching Mishna records from DB
        mishna_numbers = list(number_score_map.keys())
        mishnas = (
            session.query(Mishna)
            .filter(Mishna.number.in_(mishna_numbers))
            .all()
        )

        # Serialize and attach scores, then sort by score descending
        serialized = []
        for m in mishnas:
            data = serialize_mishna(m)
            data['similarity_score'] = number_score_map.get(m.number, 0)
            serialized.append(data)

        serialized.sort(key=lambda x: x['similarity_score'], reverse=True)

        logger.info(f'Semantic search returned {len(serialized)} results')
        _log_ai_search(session, query, serialized, _extract_user_sub_from_event(event), search_method=method)
        return success_response(serialized)

    except Exception as e:
        logger.error(f'Semantic search error: {str(e)}', exc_info=True)
        return error_response(
            'חיפוש סמנטי נכשל. אנא נסה שוב מאוחר יותר.',
            'SEARCH_FAILED', 502
        )


def _log_ai_search(session, query, results, user_sub, search_method=None):
    """Best-effort logging of an AI/semantic search query.

    Args:
        session: SQLAlchemy session.
        query: The user's search query text.
        results: List of serialized result dicts.
        user_sub: Cognito user sub or None.
        search_method: 'rag' or 'json_context' indicating which Lambda was used.
    """
    try:
        result_ids = ','.join(str(r.get('id', '')) for r in results)
        log_entry = AiSearchLog(
            query_text=query,
            result_count=len(results),
            result_ids=result_ids if result_ids else None,
            user_sub=user_sub,
            search_method=search_method,
        )
        session.add(log_entry)
        session.commit()
        logger.info(
            f'AI search logged — query length: {len(query)}, '
            f'results: {len(results)}, method: {search_method}'
        )
    except Exception as e:
        logger.warning(f'Failed to log AI search (non-critical): {str(e)}')


# ---------------------------------------------------------------------------
# Tag-based search  (GET /api/search/tags)
# ---------------------------------------------------------------------------

def _search_tags(session, params):
    """Return Mishna records associated with the given tag IDs."""
    ids_param = params.get('ids', '')

    if not ids_param:
        return error_response('חסר פרמטר תגיות', 'VALIDATION_ERROR', 400)

    # Parse comma-separated tag IDs
    tag_ids = []
    for part in ids_param.split(','):
        part = part.strip()
        if part.isdigit():
            tag_ids.append(int(part))

    if not tag_ids:
        return error_response('פרמטר תגיות לא חוקי', 'VALIDATION_ERROR', 400)

    logger.info(f'Tag search — tag IDs: {tag_ids}')

    results = (
        session.query(Mishna)
        .filter(Mishna.tags.any(Tag.id.in_(tag_ids)))
        .order_by(Mishna.number)
        .all()
    )

    logger.info(f'Found {len(results)} results')
    return success_response([serialize_mishna(m) for m in results])


# ---------------------------------------------------------------------------
# Get all tags grouped by category  (GET /api/search/tags/all)
# ---------------------------------------------------------------------------

def _get_all_tags(session):
    """Return all tags grouped by category for the tag selection UI."""
    logger.info('Fetching all tags grouped by category')

    categories = session.query(Category).all()
    tags = session.query(Tag).all()

    # Group tags by category
    cat_map = {}
    for cat in categories:
        cat_map[cat.id] = {
            'name': cat.name,
            'color': cat.color,
            'tags': [],
        }

    uncategorized = []
    for tag in tags:
        if tag.category_id and tag.category_id in cat_map:
            cat_map[tag.category_id]['tags'].append({
                'id': tag.id,
                'name': tag.name,
                'category': cat_map[tag.category_id]['name'],
            })
        else:
            uncategorized.append({
                'id': tag.id,
                'name': tag.name,
                'category': 'כללי',
            })

    # Flatten for the frontend tagSelection component
    all_tags = []
    cat_list = []
    for cat_id, cat_data in cat_map.items():
        cat_list.append({
            'id': cat_id,
            'name': cat_data['name'],
            'color': cat_data['color'],
        })
        all_tags.extend(cat_data['tags'])
    all_tags.extend(uncategorized)

    logger.info(f'Found {len(all_tags)} tags in {len(cat_list)} categories')
    return success_response({
        'tags': all_tags,
        'categories': cat_list,
    })


# ---------------------------------------------------------------------------
# Navigate by number  (GET /api/search/number/{n})
# ---------------------------------------------------------------------------

def _search_by_number(session, n_str):
    """Return a single Mishna by its sequential number (1–108)."""
    try:
        n = int(n_str)
    except (ValueError, TypeError):
        return error_response(
            'מספר משנה לא חוקי — יש להזין מספר שלם',
            'VALIDATION_ERROR', 400
        )

    if n < 1 or n > 108:
        return error_response(
            'מספר משנה חייב להיות בין 1 ל-108',
            'VALIDATION_ERROR', 400
        )

    logger.info(f'Navigate by number — n: {n}')

    mishna = session.query(Mishna).filter(Mishna.number == n).first()

    if not mishna:
        return error_response('משנה לא נמצאה', 'NOT_FOUND', 404)

    logger.info(f'Found mishna: {mishna.id}')
    return success_response(serialize_mishna(mishna))
