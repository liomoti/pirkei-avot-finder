"""API Gateway response helpers and Mishna serialization."""

import json


def success_response(body, status=200):
    """Build an API Gateway success response.

    Args:
        body: Response payload (will be JSON-serialized).
        status: HTTP status code (default 200).

    Returns:
        dict suitable for API Gateway proxy integration.
    """
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body, ensure_ascii=False)
    }


def error_response(message, code, status):
    """Build an API Gateway error response.

    Args:
        message: Hebrew user-facing error message.
        code: Machine-readable error code (e.g. VALIDATION_ERROR).
        status: HTTP status code.

    Returns:
        dict suitable for API Gateway proxy integration.
    """
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': message, 'code': code}, ensure_ascii=False)
    }


def serialize_mishna(mishna):
    """Serialize a Mishna ORM object to a JSON-ready dict.

    Includes full tag info with category name and color fallbacks.

    Args:
        mishna: A Mishna SQLAlchemy model instance.

    Returns:
        dict with all Mishna fields and nested tags.
    """
    return {
        'id': mishna.id,
        'chapter': mishna.chapter,
        'mishna': mishna.mishna,
        'number': mishna.number,
        'text_pretty': mishna.text_pretty,
        'text_raw': mishna.text_raw,
        'interpretation': mishna.interpretation,
        'pirush_url': mishna.pirush_url,
        'tags': [
            {
                'id': tag.id,
                'name': tag.name,
                'category_id': tag.category_id,
                'category_name': tag.category.name if tag.category else 'כללי',
                'category_color': tag.category.color if tag.category else '#F5F5F5'
            }
            for tag in mishna.tags
        ]
    }
