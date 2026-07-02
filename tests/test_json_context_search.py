"""Unit tests for the JSON Context Search Lambda.

Covers cache-retrieval behavior for json_context_search_handler:
  - Success path: a well-formed cache returns the mishnayot list
  - S3 read failure: 500 with code S3_ERROR
  - Missing S3_BUCKET_NAME: 500 with code INTERNAL_ERROR
  - Malformed / empty-mishnayot JSON: 500 with code INTERNAL_ERROR

Bootstrap pattern (mirrors tests/test_pbt_json_context_search.py):
  - Mock boto3 at module level so the handler's module-level client
    initialization does not require AWS credentials/region.
  - Add the function source directory to sys.path.
  - Import handler functions directly.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# --- Bootstrap: mock boto3 before importing the handler module ---------------
sys.modules['boto3'] = MagicMock()

# Add the JSON Context Search function source directory to sys.path
_FUNCTION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'functions', 'json_context_search'
)
if _FUNCTION_DIR not in sys.path:
    sys.path.insert(0, _FUNCTION_DIR)

import json_context_search_handler as h  # noqa: E402


def _make_s3_body(content):
    """Build a fake S3 get_object return value wrapping the given bytes/str.

    s3_client.get_object returns a dict whose 'Body' is a streaming object
    with a read() method. A BytesIO mimics that interface closely enough.
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    return {'Body': io.BytesIO(content)}


# A minimal but well-formed cache payload matching the documented schema.
_VALID_CACHE = {
    'mishnayot': [
        {'id': 'א_א', 'number': 1, 'text_raw': 'משה קיבל תורה מסיני', 'tags': []},
        {'id': 'א_ב', 'number': 2, 'text_raw': 'על שלושה דברים', 'tags': []},
    ],
    'tags': {},
    'generated_at': '2024-01-01T00:00:00Z',
}


class LoadMishnayotCacheTests(unittest.TestCase):
    """Unit tests for _load_mishnayot_cache(). Validates Requirements 2.3, 2.4, 2.5."""

    def _code_of(self, response):
        """Extract the error 'code' from a Lambda response body, or None."""
        return json.loads(response['body']).get('code')

    def test_success_returns_mishnayot_list(self):
        """A well-formed cache returns the mishnayot list and no error.

        Validates: Requirements 2.1, 2.2
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.return_value = _make_s3_body(
            json.dumps(_VALID_CACHE, ensure_ascii=False)
        )

        # Arrange: valid bucket name and a working S3 client
        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            # Act
            mishnayot, error = h._load_mishnayot_cache()

        # Assert: list returned, no error, correct content
        self.assertIsNone(error)
        self.assertIsInstance(mishnayot, list)
        self.assertEqual(len(mishnayot), 2)
        self.assertEqual(mishnayot[0]['number'], 1)

        # Assert: read from the correct bucket and key
        fake_s3.get_object.assert_called_once_with(
            Bucket='test-bucket', Key=h.MISHNAYOT_CACHE_KEY
        )

    def test_s3_failure_returns_500_s3_error(self):
        """An S3 read failure returns 500 with code S3_ERROR.

        Validates: Requirements 2.3
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.side_effect = Exception('S3 unavailable')

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'S3_ERROR')

    def test_missing_bucket_name_returns_500(self):
        """A missing/empty S3_BUCKET_NAME returns 500 before any S3 call.

        Validates: Requirements 2.4
        """
        fake_s3 = MagicMock()

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', ''):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'INTERNAL_ERROR')
        # No S3 read should be attempted when the bucket is unconfigured
        fake_s3.get_object.assert_not_called()

    def test_invalid_json_returns_500(self):
        """Non-JSON cache content returns 500 with code INTERNAL_ERROR.

        Validates: Requirements 2.5
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.return_value = _make_s3_body('not valid json {')

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'INTERNAL_ERROR')

    def test_missing_mishnayot_key_returns_500(self):
        """JSON without a 'mishnayot' key returns 500 INTERNAL_ERROR.

        Validates: Requirements 2.5
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.return_value = _make_s3_body(
            json.dumps({'tags': {}, 'generated_at': 'x'})
        )

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'INTERNAL_ERROR')

    def test_empty_mishnayot_list_returns_500(self):
        """An empty 'mishnayot' list returns 500 INTERNAL_ERROR.

        Validates: Requirements 2.2, 2.5
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.return_value = _make_s3_body(
            json.dumps({'mishnayot': []})
        )

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'INTERNAL_ERROR')

    def test_mishnayot_not_list_of_dicts_returns_500(self):
        """A 'mishnayot' value that is not a list of dicts returns 500.

        Validates: Requirements 2.2, 2.5
        """
        fake_s3 = MagicMock()
        fake_s3.get_object.return_value = _make_s3_body(
            json.dumps({'mishnayot': ['a', 'b', 'c']})
        )

        with patch.object(h, 's3_client', fake_s3), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            mishnayot, error = h._load_mishnayot_cache()

        self.assertIsNone(mishnayot)
        self.assertIsNotNone(error)
        self.assertEqual(error['statusCode'], 500)
        self.assertEqual(self._code_of(error), 'INTERNAL_ERROR')


if __name__ == '__main__':
    unittest.main()


def _make_converse_response(text, stop_reason='end_turn'):
    """Build a fake Bedrock Converse API response wrapping the given text.

    Mirrors the structure read by _parse_llm_response:
    response['output']['message']['content'][0]['text'].
    """
    return {
        'output': {'message': {'content': [{'text': text}]}},
        'stopReason': stop_reason,
    }


class HandlerIntegrationTests(unittest.TestCase):
    """End-to-end unit tests for handler(). Validates Requirements 1.3, 3.4, 3.6, 6.3."""

    def setUp(self):
        """Provide a working S3 client returning the valid cache by default."""
        self.fake_s3 = MagicMock()
        self.fake_s3.get_object.return_value = _make_s3_body(
            json.dumps(_VALID_CACHE, ensure_ascii=False)
        )
        self.fake_bedrock = MagicMock()

    def test_valid_payload_returns_200_with_results(self):
        """A valid payload returns 200 with a correctly formatted results body.

        Validates: Requirements 1.3, 3.6
        """
        # Arrange: bedrock returns a valid relevant_numbers JSON
        self.fake_bedrock.converse.return_value = _make_converse_response(
            '{"relevant_numbers": [2, 1]}'
        )

        with patch.object(h, 's3_client', self.fake_s3), \
                patch.object(h, 'bedrock_runtime', self.fake_bedrock), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            # Act
            response = h.handler({'query': 'ענווה'}, None)

        # Assert: standard envelope
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(
            response['headers']['Content-Type'], 'application/json'
        )
        self.assertEqual(
            response['headers']['Access-Control-Allow-Origin'], '*'
        )

        # Assert: body is a JSON string with a results dict
        body = json.loads(response['body'])
        self.assertIn('results', body)
        results = body['results']
        self.assertIsInstance(results, dict)
        # Two numbers returned, first scores exactly 1.0, keys are strings
        self.assertEqual(results['2'], 1.0)
        self.assertEqual(results['1'], 0.5)

    def test_converse_failure_returns_500_hebrew_message(self):
        """A Converse API failure returns 500 with the Hebrew error message.

        Validates: Requirements 3.6, 6.3
        """
        self.fake_bedrock.converse.side_effect = Exception('bedrock down')

        with patch.object(h, 's3_client', self.fake_s3), \
                patch.object(h, 'bedrock_runtime', self.fake_bedrock), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            response = h.handler({'query': 'ענווה'}, None)

        self.assertEqual(response['statusCode'], 500)
        body = json.loads(response['body'])
        self.assertEqual(body['error'], 'אירעה שגיאה פנימית')
        self.assertEqual(body['code'], 'INTERNAL_ERROR')

    def test_non_end_turn_stop_reason_continues(self):
        """A non-end_turn stop reason logs a warning and still returns 200.

        Validates: Requirements 3.6
        """
        self.fake_bedrock.converse.return_value = _make_converse_response(
            '{"relevant_numbers": [1]}', stop_reason='max_tokens'
        )

        with patch.object(h, 's3_client', self.fake_s3), \
                patch.object(h, 'bedrock_runtime', self.fake_bedrock), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'), \
                patch.object(h.logger, 'warning') as mock_warning:
            response = h.handler({'query': 'ענווה'}, None)

        # Processing continues despite the non-end_turn stop reason
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['results']['1'], 1.0)

        # A warning was logged mentioning the stop reason
        self.assertTrue(
            any('max_tokens' in str(call) for call in mock_warning.call_args_list)
        )

    def test_converse_call_uses_correct_inference_config_and_system_prompt(self):
        """The converse call uses temperature 0.0/maxTokens 1000 and a
        system prompt with the required instructions.

        Validates: Requirements 3.4
        """
        self.fake_bedrock.converse.return_value = _make_converse_response(
            '{"relevant_numbers": []}'
        )

        with patch.object(h, 's3_client', self.fake_s3), \
                patch.object(h, 'bedrock_runtime', self.fake_bedrock), \
                patch.object(h, 'S3_BUCKET_NAME', 'test-bucket'):
            h.handler({'query': 'ענווה'}, None)

        # Inspect the converse call kwargs
        self.assertEqual(self.fake_bedrock.converse.call_count, 1)
        _, kwargs = self.fake_bedrock.converse.call_args

        # Model ID
        self.assertEqual(kwargs['modelId'], h.MODEL_ID)

        # Inference config: deterministic with maxTokens 1000
        self.assertEqual(kwargs['inferenceConfig']['temperature'], 0.0)
        self.assertEqual(kwargs['inferenceConfig']['maxTokens'], 1000)

        # System prompt contains the required instructions
        system_text = kwargs['system'][0]['text']
        self.assertIn('Pirkei Avot', system_text)
        self.assertIn('relevant_numbers', system_text)
        self.assertIn('1-108', system_text)

        # User message embeds the query and the serialized mishnayot JSON
        user_text = kwargs['messages'][0]['content'][0]['text']
        self.assertIn('ענווה', user_text)
        self.assertIn('משה קיבל תורה מסיני', user_text)
