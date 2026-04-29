"""Settings handler Lambda function for Pirkei Avot Finder.

Routes the public GET /api/settings and the authenticated
PUT /api/settings/pirush endpoints. JWT validation on the PUT
route is handled by the API Gateway Cognito authorizer.
"""

import json
import logging

from sqlalchemy.exc import SQLAlchemyError

from db import Session
from models import get_pirush_settings, set_pirush_enabled
from response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct settings function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'Settings handler invoked: {method} {path}')

    session = Session()
    try:
        # GET /api/settings
        if path == '/api/settings' and method == 'GET':
            return _get_settings(session)

        # PUT /api/settings/pirush
        elif path == '/api/settings/pirush' and method == 'PUT':
            return _update_pirush(session, event)

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
# Settings endpoints
# ---------------------------------------------------------------------------

def _get_settings(session):
    """Return pirush_enabled and pirush_attribution_url."""
    logger.info('Fetching site settings')

    settings = get_pirush_settings(session)

    logger.info(f'Settings retrieved — pirush_enabled: {settings["pirush_enabled"]}')
    return success_response(settings)


def _update_pirush(session, event):
    """Upsert pirush_enabled in SiteSetting table."""
    body = _parse_body(event)

    enabled = body.get('enabled')
    if enabled is None or not isinstance(enabled, bool):
        return error_response('חסר שדה enabled (boolean)', 'VALIDATION_ERROR', 400)

    logger.info(f'Updating pirush_enabled to {enabled}')

    try:
        set_pirush_enabled(session, enabled)
        logger.info(f'pirush_enabled updated to {enabled}')
        return success_response({
            'message': 'ההגדרה עודכנה בהצלחה',
            'pirush_enabled': enabled,
        })

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f'Database error while updating pirush setting: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה בשמירת הנתונים', 'INTERNAL_ERROR', 500)
