"""Auth handler Lambda function for Pirkei Avot Finder.

Routes login, logout, registration, and password reset endpoints.
Uses Amazon Cognito for authentication via the USER_PASSWORD_AUTH flow.
"""

import base64
import json
import logging
import os
import re

import boto3

from response import success_response, error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cognito client initialized at module level — persists across warm invocations
cognito_client = boto3.client('cognito-idp')
COGNITO_USER_POOL_CLIENT_ID = os.environ.get('COGNITO_USER_POOL_CLIENT_ID', '')
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID', '')


def handler(event, context):
    """Main Lambda entry point — dispatches to the correct auth function."""
    path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')

    logger.info(f'Auth handler invoked: {method} {path}')

    try:
        # POST /api/auth/register
        if path == '/api/auth/register' and method == 'POST':
            return _register(event)

        # POST /api/auth/login
        elif path == '/api/auth/login' and method == 'POST':
            return _login(event)

        # POST /api/auth/logout
        elif path == '/api/auth/logout' and method == 'POST':
            return _logout()

        # POST /api/auth/forgot-password
        elif path == '/api/auth/forgot-password' and method == 'POST':
            return _forgot_password(event)

        # POST /api/auth/confirm-reset
        elif path == '/api/auth/confirm-reset' and method == 'POST':
            return _confirm_reset(event)

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


def _validate_password_policy(password):
    """Return True if password meets the policy: min 8 chars, uppercase, lowercase, digit."""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True


def _decode_jwt_payload(token):
    """Decode the JWT payload (middle part) and return it as a dict."""
    parts = token.split('.')
    if len(parts) < 2:
        return {}

    # Fix base64 padding
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += '=' * padding

    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

def _register(event):
    """Register a new user via Cognito sign_up and immediately auto-confirm.

    Expects JSON body with 'email' and 'password' fields.
    Assigns custom:role='user' to the new account.
    Returns success message on creation, 409 if email already exists.
    """
    body = _parse_body(event)

    email = body.get('email', '').strip()
    password = body.get('password', '')

    if not email or not password:
        return error_response('חסרים שדות חובה: email, password', 'VALIDATION_ERROR', 400)

    if not _validate_password_policy(password):
        return error_response(
            'הסיסמה חייבת להכיל לפחות 8 תווים, אות גדולה, אות קטנה ומספר',
            'VALIDATION_ERROR',
            400,
        )

    logger.info(f'Registration attempt for: {email}')

    try:
        cognito_client.sign_up(
            ClientId=COGNITO_USER_POOL_CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[{'Name': 'custom:role', 'Value': 'user'}],
        )

        # Auto-confirm the user so they can log in immediately
        cognito_client.admin_confirm_sign_up(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
        )

        logger.info(f'Registration successful for: {email}')
        return success_response(
            {'message': 'ההרשמה הושלמה בהצלחה. ניתן להתחבר כעת.', 'email': email},
            201,
        )

    except cognito_client.exceptions.UsernameExistsException:
        logger.warning(f'Registration failed — email already exists: {email}')
        return error_response('כתובת האימייל כבר רשומה במערכת', 'DUPLICATE_ENTRY', 409)

    except Exception as e:
        logger.error(f'Cognito error during registration: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה באימות', 'INTERNAL_ERROR', 500)


def _login(event):
    """Authenticate against Cognito with USER_PASSWORD_AUTH flow.

    Expects JSON body with 'email' and 'password' fields.
    Returns JWT token and user role on success, 401 on invalid credentials,
    403 if the account is disabled.
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

        # Decode JWT payload to extract the user role
        payload = _decode_jwt_payload(id_token)
        role = payload.get('custom:role', 'user')

        logger.info(f'Login successful for: {email}, role: {role}')
        return success_response({
            'token': id_token,
            'role': role,
            'expires_in': expires_in,
        })

    except cognito_client.exceptions.NotAuthorizedException as e:
        error_msg = str(e)
        if 'disabled' in error_msg.lower():
            logger.warning(f'Login failed — account disabled: {email}')
            return error_response(
                'החשבון שלך מושבת. אנא פנה למנהל המערכת',
                'FORBIDDEN',
                403,
            )
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


def _forgot_password(event):
    """Initiate a password reset flow via Cognito.

    Expects JSON body with 'email' field.
    Always returns a generic success message to prevent email enumeration.
    """
    body = _parse_body(event)
    email = body.get('email', '').strip()

    logger.info(f'Forgot password requested for: {email}')

    try:
        cognito_client.forgot_password(
            ClientId=COGNITO_USER_POOL_CLIENT_ID,
            Username=email,
        )
    except Exception as e:
        # Swallow all errors — return generic success to prevent email enumeration
        logger.warning(f'Forgot password error (suppressed): {str(e)}')

    return success_response({'message': 'קוד איפוס נשלח לכתובת האימייל'})


def _confirm_reset(event):
    """Confirm a password reset using the code sent to the user's email.

    Expects JSON body with 'email', 'code', and 'new_password' fields.
    Returns success on valid code + new password, or descriptive errors.
    """
    body = _parse_body(event)

    email = body.get('email', '').strip()
    code = body.get('code', '').strip()
    new_password = body.get('new_password', '')

    if not email or not code or not new_password:
        return error_response('חסרים שדות חובה: email, code, new_password', 'VALIDATION_ERROR', 400)

    logger.info(f'Confirm reset requested for: {email}')

    try:
        cognito_client.confirm_forgot_password(
            ClientId=COGNITO_USER_POOL_CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )

        logger.info(f'Password reset successful for: {email}')
        return success_response({'message': 'הסיסמה אופסה בהצלחה'})

    except cognito_client.exceptions.CodeMismatchException:
        logger.warning(f'Confirm reset failed — code mismatch for: {email}')
        return error_response('הקוד שהוזן שגוי', 'VALIDATION_ERROR', 400)

    except cognito_client.exceptions.ExpiredCodeException:
        logger.warning(f'Confirm reset failed — expired code for: {email}')
        return error_response('הקוד פג תוקף. אנא בקש קוד חדש', 'VALIDATION_ERROR', 400)

    except cognito_client.exceptions.InvalidPasswordException:
        logger.warning(f'Confirm reset failed — invalid password policy for: {email}')
        return error_response(
            'הסיסמה החדשה אינה עומדת בדרישות המדיניות',
            'VALIDATION_ERROR',
            400,
        )

    except Exception as e:
        logger.error(f'Cognito error during confirm reset: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה באימות', 'INTERNAL_ERROR', 500)
