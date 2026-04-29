"""Auth handler Lambda function for Pirkei Avot Finder.

Routes login and logout endpoints. Uses Amazon Cognito for
admin authentication via the USER_PASSWORD_AUTH flow.
"""

import json
import logging
import os

import boto3

from response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito client initialized at module level — persists across warm invocations
cognito_client = boto3.client('cognito-idp')
COGNITO_USER_POOL_CLIENT_ID = os.environ.get('COGNITO_USER_POOL_CLIENT_ID', '')


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct auth function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'Auth handler invoked: {method} {path}')

    try:
        # POST /api/auth/login
        if path == '/api/auth/login' and method == 'POST':
            return _login(event)

        # POST /api/auth/logout
        elif path == '/api/auth/logout' and method == 'POST':
            return _logout()

        else:
            return error_response('הנתיב המבוקש לא נמצא', 'NOT_FOUND', 404)

    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה פנימית', 'INTERNAL_ERROR', 500)


def _parse_body(event):
    """Parse JSON body from the event, handling both string and dict formats."""
    body = event.get('body', '{}')
    if isinstance(body, str):
        return json.loads(body)
    return body


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

def _login(event):
    """Authenticate against Cognito with USER_PASSWORD_AUTH flow.

    Expects JSON body with 'email' and 'password' fields.
    Returns JWT token on success, 401 on invalid credentials.
    """
    body = _parse_body(event)

    email = body.get('email', '').strip()
    password = body.get('password', '')

    if not email or not password:
        return error_response('חסרים שדות חובה: email, password', 'VALIDATION_ERROR', 400)

    logger.info(f'Login attempt for: {email}')

    try:
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_USER_POOL_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password,
            },
        )

        auth_result = response.get('AuthenticationResult', {})
        id_token = auth_result.get('IdToken', '')
        expires_in = auth_result.get('ExpiresIn', 3600)

        logger.info(f'Login successful for: {email}')
        return success_response({
            'token': id_token,
            'expires_in': expires_in,
        })

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning(f'Login failed — invalid credentials for: {email}')
        return error_response('שם משתמש או סיסמה שגויים', 'AUTH_REQUIRED', 401)

    except cognito_client.exceptions.UserNotFoundException:
        logger.warning(f'Login failed — user not found: {email}')
        return error_response('שם משתמש או סיסמה שגויים', 'AUTH_REQUIRED', 401)

    except Exception as e:
        logger.error(f'Cognito error during login: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה באימות', 'INTERNAL_ERROR', 500)


def _logout():
    """Return success — frontend handles token clearing."""
    logger.info('Logout requested')
    return success_response({'message': 'התנתקת בהצלחה'})
