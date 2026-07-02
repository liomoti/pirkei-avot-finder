"""Settings handler Lambda function for Pirkei Avot Finder.

Routes the public GET /api/settings and the authenticated
PUT /api/settings/pirush endpoints. JWT validation on the PUT
route is handled by the API Gateway Cognito authorizer.
"""

import json
import logging

from sqlalchemy.exc import SQLAlchemyError

from db import Session
from models import get_pirush_settings, get_pirush_options, set_pirush_enabled, set_pirush_options
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

        # POST /api/settings/pirush/options
        elif path == '/api/settings/pirush/options' and method == 'POST':
            return _add_pirush_option(session, event)

        # DELETE /api/settings/pirush/options
        elif path == '/api/settings/pirush/options' and method == 'DELETE':
            return _delete_pirush_option(session, event)

        # PUT /api/settings/pirush/options
        elif path == '/api/settings/pirush/options' and method == 'PUT':
            return _update_pirush_option(session, event)

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
    """Return pirush_enabled, pirush_attribution_url, and pirush_options."""
    logger.info('Fetching site settings')

    settings = get_pirush_settings(session)
    settings['pirush_options'] = get_pirush_options(session)

    logger.info(f'Settings retrieved — pirush_enabled: {settings["pirush_enabled"]}')
    return success_response(settings)


def _update_pirush_option(session, event):
    """Toggle enabled state of a PirushOption by internal_name."""
    body = _parse_body(event)
    internal_name = body.get('internal_name', '')
    enabled = body.get('enabled', True)

    options = get_pirush_options(session)
    for option in options:
        if option.get('internal_name') == internal_name:
            option['enabled'] = enabled
            break
    set_pirush_options(session, options)
    return success_response({'message': 'ההגדרה עודכנה בהצלחה', 'options': options})


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


def _add_pirush_option(session, event):
    """Append a new PirushOption to the pirush_options list."""
    body = _parse_body(event)
    s3_url = body.get('s3_url', '')
    internal_name = body.get('internal_name', '')
    button_label = body.get('button_label', '')

    options = get_pirush_options(session)
    options.append({
        's3_url': s3_url,
        'internal_name': internal_name,
        'button_label': button_label,
        'enabled': True,
    })
    set_pirush_options(session, options)
    return success_response({'message': 'אפשרות הפירוש נוספה בהצלחה', 'options': options})


def _delete_pirush_option(session, event):
    """Remove a PirushOption by internal_name."""
    body = _parse_body(event)
    internal_name = body.get('internal_name', '')

    options = get_pirush_options(session)
    updated = [o for o in options if o.get('internal_name') != internal_name]
    set_pirush_options(session, updated)
    return success_response({'message': 'אפשרות הפירוש הוסרה בהצלחה', 'options': updated})
