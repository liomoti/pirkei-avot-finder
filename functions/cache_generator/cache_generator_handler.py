"""Cache Generator Lambda function for Pirkei Avot Finder.

Generates a static JSON cache file containing all mishnayot with their
tags and categories, uploads it to S3, and invalidates the CloudFront
cache. Triggered by the Admin Lambda via synchronous invocation.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from db import Session
from models import Mishna, Tag, Category
from response import success_response, error_response, serialize_mishna

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
CLOUDFRONT_DISTRIBUTION_ID = os.environ.get('CLOUDFRONT_DISTRIBUTION_ID', '')

s3_client = boto3.client('s3')
cloudfront_client = boto3.client('cloudfront')


def handler(event, context):
    """Generate the static mishnaiot cache JSON and upload to S3."""
    logger.info('Cache generator invoked')

    session = Session()
    try:
        cache_data = _build_cache_json(session)
        generated_at = cache_data['generated_at']
        count = len(cache_data['mishnayot'])

        json_bytes = json.dumps(cache_data, ensure_ascii=False).encode('utf-8')

        _upload_to_s3(json_bytes, S3_BUCKET_NAME, 'static/mishnaiot.json')

        _invalidate_cloudfront(CLOUDFRONT_DISTRIBUTION_ID, '/static/mishnaiot.json')

        logger.info(f'Cache generated successfully — {count} mishnayot, generated_at: {generated_at}')
        return success_response({
            'message': 'המטמון נוצר בהצלחה',
            'generated_at': generated_at,
            'count': count,
        })

    except SQLAlchemyError as e:
        logger.error(f'Database error: {str(e)}', exc_info=True)
        return error_response('שגיאה בגישה למסד הנתונים', 'INTERNAL_ERROR', 500)
    except ClientError as e:
        logger.error(f'S3 error: {str(e)}', exc_info=True)
        return error_response('שגיאה בהעלאת הקובץ ל-S3', 'S3_ERROR', 500)
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}', exc_info=True)
        return error_response('אירעה שגיאה פנימית', 'INTERNAL_ERROR', 500)
    finally:
        session.close()


def _build_cache_json(session):
    """Query DB, serialize all mishnayot and tags, return cache dict.

    Args:
        session: SQLAlchemy session instance.

    Returns:
        dict with 'mishnayot', 'tags', and 'generated_at' keys.
    """
    # Query all mishnayot with eager-loaded tags and categories
    mishnayot = (
        session.query(Mishna)
        .options(joinedload(Mishna.tags).joinedload(Tag.category))
        .order_by(Mishna.number)
        .all()
    )

    # Serialize each mishna using the shared serialize_mishna function
    serialized_mishnayot = [serialize_mishna(m) for m in mishnayot]

    # Build tags section matching _get_all_tags() shape from search_handler.py
    categories = session.query(Category).all()
    tags = session.query(Tag).all()

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

    generated_at = datetime.now(timezone.utc).isoformat()

    logger.info(f'Built cache — {len(serialized_mishnayot)} mishnayot, {len(all_tags)} tags, {len(cat_list)} categories')

    return {
        'mishnayot': serialized_mishnayot,
        'tags': {
            'tags': all_tags,
            'categories': cat_list,
        },
        'generated_at': generated_at,
    }


def _upload_to_s3(json_bytes, bucket, key):
    """Upload JSON bytes to S3 with correct content type.

    Args:
        json_bytes: UTF-8 encoded JSON bytes.
        bucket: S3 bucket name.
        key: S3 object key.

    Raises:
        ClientError: If the S3 upload fails.
    """
    logger.info(f'Uploading cache to s3://{bucket}/{key} ({len(json_bytes)} bytes)')

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_bytes,
        ContentType='application/json; charset=utf-8',
    )

    logger.info('S3 upload completed')


def _invalidate_cloudfront(distribution_id, path):
    """Create a CloudFront invalidation (best-effort).

    Logs a warning on failure but does not raise — invalidation
    is not critical to the cache generation operation.

    Args:
        distribution_id: CloudFront distribution ID.
        path: The path to invalidate (e.g. '/static/mishnaiot.json').
    """
    if not distribution_id:
        logger.warning('CLOUDFRONT_DISTRIBUTION_ID not set — skipping invalidation')
        return

    try:
        caller_reference = f'cache-gen-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'

        cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': [path],
                },
                'CallerReference': caller_reference,
            },
        )

        logger.info(f'CloudFront invalidation created for {path}')

    except Exception as e:
        logger.warning(f'CloudFront invalidation failed (non-critical): {str(e)}')
