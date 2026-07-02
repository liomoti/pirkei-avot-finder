"""JSON Context Search Lambda function for Pirkei Avot Finder.

Performs semantic search by passing the full cached mishnayot JSON
(static/mishnaiot.json) as context to Amazon Nova Pro via the Bedrock
Converse API. The LLM identifies relevant mishnayot using text content,
tags, and categories, returning a relevance-scored results dictionary.

Invoked directly via Lambda-to-Lambda invoke from the Search Handler.
"""

import json
import logging
import os

import boto3
from urllib.parse import unquote_plus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients initialized at module level — persist across warm invocations
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime')

S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')

MODEL_ID = 'us.amazon.nova-pro-v1:0'
MISHNAYOT_CACHE_KEY = 'static/mishnaiot.json'
MAX_QUERY_LENGTH = 500


def handler(event, context):
    """Lambda entry point for JSON-context semantic search queries.

    Accepts a direct Lambda invoke payload with a 'query' key. Validates
    the query, then (in later stages) loads the mishnayot cache, queries
    the LLM, and returns a relevance-scored results dictionary.

    Returns a response dict with statusCode, headers, and a JSON body.
    """
    logger.info(f'Received event: {json.dumps(event)}')

    try:
        # Validate and extract the query — returns either a (query, None)
        # tuple on success or (None, error_response) on failure
        query, error = _validate_query(event)
        if error is not None:
            return error

        logger.info(f'Processing search query: {query!r}')

        # Load the full mishnayot cache from S3 for LLM context
        mishnayot, error = _load_mishnayot_cache()
        if error is not None:
            return error

        # Query Nova Pro with the full JSON context
        llm_response, error = _query_llm(query, mishnayot)
        if error is not None:
            return error

        # Parse the LLM output and convert to a scored results dict
        relevant_numbers = _parse_llm_response(llm_response)
        results = _build_results(relevant_numbers)

        logger.info(
            f'Search complete — query: {query!r}, '
            f'mishnayot loaded: {len(mishnayot)}, results: {len(results)}'
        )

        return _build_response(200, {'results': results})

    except Exception as e:
        logger.error(f'Unexpected error in handler: {str(e)}', exc_info=True)
        return _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'}
        )


def _validate_query(event):
    """Extract and validate the query from the invoke payload.

    Reads the 'query' key, URL-decodes it, and trims whitespace. Rejects
    missing/empty/whitespace-only queries and queries longer than 500
    characters with a 400 VALIDATION_ERROR response.

    Returns a (query, None) tuple on success, or (None, error_response)
    when validation fails.
    """
    raw_query = event.get('query')

    if raw_query is None:
        logger.warning('Request rejected: No query provided')
        return None, _build_response(
            400,
            {'error': 'חסר טקסט לחיפוש', 'code': 'VALIDATION_ERROR'}
        )

    # URL-decode before any validation or processing
    decoded_query = unquote_plus(str(raw_query))

    if decoded_query.strip() == '':
        logger.warning('Request rejected: Empty query after trimming')
        return None, _build_response(
            400,
            {'error': 'חסר טקסט לחיפוש', 'code': 'VALIDATION_ERROR'}
        )

    if len(decoded_query) > MAX_QUERY_LENGTH:
        logger.warning(
            f'Request rejected: Query too long ({len(decoded_query)} chars)'
        )
        return None, _build_response(
            400,
            {'error': 'השאילתה ארוכה מדי', 'code': 'VALIDATION_ERROR'}
        )

    return decoded_query.strip(), None


def _load_mishnayot_cache():
    """Load and parse the mishnayot cache (static/mishnaiot.json) from S3.

    Reads the cache object from the configured S3 bucket, parses the JSON
    content, and extracts the 'mishnayot' array, which must be a non-empty
    list of dictionaries for use as LLM context.

    Returns a (mishnayot_list, None) tuple on success, or
    (None, error_response) when the bucket is unconfigured, the S3 read
    fails, or the content is invalid/empty.
    """
    if not S3_BUCKET_NAME:
        logger.error('S3_BUCKET_NAME not configured')
        return None, _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'}
        )

    # Read the cache object from S3 — infrastructure failures are fatal
    try:
        s3_response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME, Key=MISHNAYOT_CACHE_KEY
        )
        raw_content = s3_response['Body'].read()
    except Exception as e:
        logger.error(
            f'Failed to read {MISHNAYOT_CACHE_KEY} from S3: {str(e)}',
            exc_info=True
        )
        return None, _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'S3_ERROR'}
        )

    # Parse and validate the JSON structure
    try:
        data = json.loads(raw_content)
    except (ValueError, TypeError) as e:
        logger.error(f'Failed to parse mishnayot cache JSON: {str(e)}')
        return None, _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'}
        )

    mishnayot = data.get('mishnayot') if isinstance(data, dict) else None

    if not isinstance(mishnayot, list) or not mishnayot or \
            not all(isinstance(m, dict) for m in mishnayot):
        logger.error(
            'Invalid mishnayot cache: missing or empty "mishnayot" list'
        )
        return None, _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'}
        )

    logger.info(f'Loaded {len(mishnayot)} mishnayot from cache')
    return mishnayot, None


def _query_llm(query, mishnayot):
    """Query Nova Pro via the Bedrock Converse API with full JSON context.

    Sends a system prompt instructing the model to act as a Torah scholar
    expert in Pirkei Avot and a user message containing the query plus the
    full mishnayot JSON array. Uses deterministic inference (temperature 0.0).

    Returns a (converse_response, None) tuple on success, or
    (None, error_response) when the Converse API call fails. The raw
    Converse response is returned for the parsing stage to handle.
    """
    system_prompt = """You are an expert Torah scholar specializing in 'Pirkei Avot' (Ethics of the Fathers).
Your Task:
1. Deeply analyze the conceptual and semantic meaning of the User's Query (in Hebrew).
2. Review the full list of Mishnayot provided as JSON. Each mishna includes its text content, tags, and categories.
3. Identify the Mishnayot that are most relevant to the query using their text content, tags, and categories.
4. Order the relevant Mishnayot from most relevant to least relevant.

Output Requirement:
You must output strictly a VALID JSON Object. No preamble, no markdown code blocks (```json), no explanation.
Format: {"relevant_numbers": [3, 15, 42]}
The "relevant_numbers" array must contain only integers in the range 1-108, limited to at most 20 results.
If no mishna is relevant at all, return {"relevant_numbers": []}"""

    user_message = f"""User Query: "{query}"

Mishnayot:
{json.dumps(mishnayot, ensure_ascii=False)}"""

    try:
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=[{
                'role': 'user',
                'content': [{'text': user_message}]
            }],
            system=[{'text': system_prompt}],
            inferenceConfig={'temperature': 0.0, 'maxTokens': 1000}
        )
    except Exception as e:
        logger.error(f'Converse API call failed: {str(e)}', exc_info=True)
        return None, _build_response(
            500,
            {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'}
        )

    # Non-end_turn stop reasons (e.g. truncation) are logged but tolerated —
    # the parsing stage handles whatever partial output was returned
    stop_reason = response.get('stopReason')
    if stop_reason != 'end_turn':
        logger.warning(f'Converse returned non-end_turn stop reason: {stop_reason}')

    return response, None


def _parse_llm_response(response):
    """Extract the relevant mishna numbers from a Converse API response.

    Safely reads the LLM output text from the Converse response object,
    strips any markdown code-block markers, and extracts the JSON object
    between the first '{' and last '}'. Reads the 'relevant_numbers' array,
    keeping only integers in the range 1-108 (excluding booleans) while
    preserving their order.

    Returns an empty list when the output is empty, contains no '{', is not
    valid JSON, or is missing the 'relevant_numbers' key.
    """
    # Safely extract the output text from the Converse response envelope
    try:
        output_text = response['output']['message']['content'][0]['text']
    except (KeyError, IndexError, TypeError):
        output_text = ''

    logger.info(f'Raw LLM output: {output_text!r}')

    if not output_text:
        logger.warning('LLM output text is empty; returning empty results')
        return []

    # Strip markdown code-block markers (```json ... ``` or ``` ... ```)
    stripped = output_text.replace('```json', '').replace('```', '').strip()

    start = stripped.find('{')
    end = stripped.rfind('}')

    if start == -1 or end == -1 or end < start:
        logger.warning('LLM output contains no JSON object; returning empty results')
        return []

    json_text = stripped[start:end + 1]

    try:
        data = json.loads(json_text)
    except (ValueError, TypeError) as e:
        logger.error(f'Failed to parse LLM JSON output: {str(e)}')
        return []

    if not isinstance(data, dict) or 'relevant_numbers' not in data:
        logger.warning(
            'LLM output missing "relevant_numbers" key; returning empty results'
        )
        return []

    raw_numbers = data.get('relevant_numbers')
    if not isinstance(raw_numbers, list):
        logger.warning(
            '"relevant_numbers" is not a list; returning empty results'
        )
        return []

    # Keep only true integers (excluding bools) in the range 1-108, in order
    relevant_numbers = [
        n for n in raw_numbers
        if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 108
    ]

    return relevant_numbers


def _build_results(relevant_numbers):
    """Convert an ordered list of mishna numbers into a scored results dict.

    Assigns descending relevance scores preserving the LLM's ordering: for
    N numbers, the i-th number (0-indexed) receives a score of
    `1.0 - i * (1.0 / N)`, so the first item always scores exactly 1.0.
    Keys are the string representations of the mishna numbers.

    Returns an empty dict when the input list is empty.
    """
    n = len(relevant_numbers)
    if n == 0:
        return {}

    step = 1.0 / n
    return {
        str(number): 1.0 - i * step
        for i, number in enumerate(relevant_numbers)
    }


def _build_response(status_code, body):
    """Build a Lambda response with the standard envelope and headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        },
        'body': json.dumps(body, ensure_ascii=False),
    }
