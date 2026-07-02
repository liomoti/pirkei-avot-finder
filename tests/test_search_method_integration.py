"""Unit tests for the Settings Handler semantic-search-method endpoint.

Covers settings_handler behavior for Requirement 10.2 and 10.3:
  - PUT /api/settings/semantic-search-method with a valid 'rag' value upserts
    correctly and returns a success response
  - PUT /api/settings/semantic-search-method with a valid 'json_context' value
    upserts correctly and returns a success response
  - GET /api/settings includes the semantic_search_method key in the body

Bootstrap pattern (mirrors tests/test_json_context_search.py):
  - Mock boto3 and the db module at module level so importing the settings
    handler (which imports the shared layer's db/models) does not require AWS
    credentials or a live database.
  - Add the shared layer and the settings function source directories to
    sys.path.
  - Import settings_handler directly and patch the model helper functions that
    it imported at module load time.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# --- Bootstrap: mock boto3 and db before importing the handler module --------
sys.modules['boto3'] = MagicMock()
sys.modules['db'] = MagicMock()

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Shared layer provides models/response; settings dir provides the handler;
# search dir provides the search handler used for routing tests.
_SHARED_DIR = os.path.join(_ROOT, 'layers', 'shared')
_SETTINGS_DIR = os.path.join(_ROOT, 'functions', 'settings')
_SEARCH_DIR = os.path.join(_ROOT, 'functions', 'search')
for _p in (_SHARED_DIR, _SETTINGS_DIR, _SEARCH_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import settings_handler as h  # noqa: E402
import search_handler as sh  # noqa: E402


def _put_event(body):
    """Build an API Gateway v2 event for PUT /api/settings/semantic-search-method."""
    return {
        'rawPath': '/api/settings/semantic-search-method',
        'requestContext': {'http': {'method': 'PUT'}},
        'body': json.dumps(body),
    }


def _get_event():
    """Build an API Gateway v2 event for GET /api/settings."""
    return {
        'rawPath': '/api/settings',
        'requestContext': {'http': {'method': 'GET'}},
    }


class UpdateSemanticSearchMethodTests(unittest.TestCase):
    """PUT /api/settings/semantic-search-method. Validates Requirements 10.3."""

    def test_valid_rag_upserts_and_returns_success(self):
        """A valid 'rag' value calls set_semantic_search_method and succeeds.

        Validates: Requirements 10.3
        """
        fake_set = MagicMock()
        # Patch the model helpers imported into the handler module.
        with patch.object(h, 'set_semantic_search_method', fake_set):
            response = h.handler(_put_event({'method': 'rag'}), None)

        # set_semantic_search_method called with the submitted value
        fake_set.assert_called_once()
        self.assertEqual(fake_set.call_args.args[1], 'rag')

        # Success response echoing the persisted value
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['semantic_search_method'], 'rag')

    def test_valid_json_context_upserts_and_returns_success(self):
        """A valid 'json_context' value upserts and returns success.

        Validates: Requirements 10.3
        """
        fake_set = MagicMock()
        with patch.object(h, 'set_semantic_search_method', fake_set):
            response = h.handler(_put_event({'method': 'json_context'}), None)

        fake_set.assert_called_once()
        self.assertEqual(fake_set.call_args.args[1], 'json_context')

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['semantic_search_method'], 'json_context')

    def test_invalid_method_returns_400_and_does_not_upsert(self):
        """An invalid method value returns 400 VALIDATION_ERROR without upsert.

        Validates: Requirements 10.3
        """
        fake_set = MagicMock()
        with patch.object(h, 'set_semantic_search_method', fake_set):
            response = h.handler(_put_event({'method': 'bogus'}), None)

        fake_set.assert_not_called()
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['code'], 'VALIDATION_ERROR')


class GetSettingsIncludesMethodTests(unittest.TestCase):
    """GET /api/settings includes semantic_search_method. Validates Requirements 10.2."""

    def test_get_settings_includes_semantic_search_method(self):
        """GET /api/settings response body contains semantic_search_method.

        Validates: Requirements 10.2
        """
        fake_get_pirush = MagicMock(return_value={
            'pirush_enabled': True,
            'pirush_attribution_url': 'https://example.com',
        })
        fake_get_method = MagicMock(return_value='json_context')

        with patch.object(h, 'get_pirush_settings', fake_get_pirush), \
                patch.object(h, 'get_semantic_search_method', fake_get_method):
            response = h.handler(_get_event(), None)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertIn('semantic_search_method', body)
        self.assertEqual(body['semantic_search_method'], 'json_context')

    def test_get_settings_method_defaults_to_rag(self):
        """When the helper returns 'rag', the response reflects that default.

        Validates: Requirements 10.2
        """
        fake_get_pirush = MagicMock(return_value={
            'pirush_enabled': False,
            'pirush_attribution_url': '',
        })
        fake_get_method = MagicMock(return_value='rag')

        with patch.object(h, 'get_pirush_settings', fake_get_pirush), \
                patch.object(h, 'get_semantic_search_method', fake_get_method):
            response = h.handler(_get_event(), None)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['semantic_search_method'], 'rag')


class SearchMethodRoutingProperties(unittest.TestCase):
    """Property-based tests for Search Handler routing.

    Feature: json-context-semantic-search, Property 10: Search method routing
    selects correct Lambda.
    """

    @settings(max_examples=100)
    @given(method=st.sampled_from(['rag', 'json_context']))
    def test_routing_selects_correct_lambda(self, method):
        """The resolved method picks the matching function-name env var.

        Feature: json-context-semantic-search, Property 10: Search method
        routing selects correct Lambda (rag -> SEMANTIC_SEARCH_FUNCTION_NAME,
        json_context -> JSON_CONTEXT_SEARCH_FUNCTION_NAME).

        Validates: Requirements 10.5, 10.6
        """
        # Arrange: distinct sentinel function names per method
        rag_name = 'sentinel-rag-fn'
        json_name = 'sentinel-json-context-fn'
        expected = json_name if method == 'json_context' else rag_name

        # Mock the lambda invoke response far enough to reach FunctionName
        # selection: an empty-results payload short-circuits after invoke.
        fake_payload = MagicMock()
        fake_payload.read.return_value = json.dumps({'results': {}}).encode()
        fake_invoke = MagicMock(return_value={'Payload': fake_payload})

        env = {
            'SEMANTIC_SEARCH_FUNCTION_NAME': rag_name,
            'JSON_CONTEXT_SEARCH_FUNCTION_NAME': json_name,
        }

        # Act: drive _semantic_search with the parametrized active method.
        with patch.dict(os.environ, env, clear=False), \
                patch.object(sh, 'get_semantic_search_method',
                             return_value=method), \
                patch.object(sh.lambda_client, 'invoke', fake_invoke), \
                patch.object(sh, '_log_ai_search', MagicMock()):
            sh._semantic_search(MagicMock(), 'מה אומרים על ענווה?', {})

        # Assert: invoke received the FunctionName matching the active method.
        fake_invoke.assert_called_once()
        self.assertEqual(
            fake_invoke.call_args.kwargs['FunctionName'], expected
        )


class SearchMethodLoggingProperties(unittest.TestCase):
    """Property-based tests for AiSearchLog method logging.

    Feature: json-context-semantic-search, Property 11: Search method is logged
    in AiSearchLog.
    """

    @settings(max_examples=100)
    @given(
        method=st.sampled_from(['rag', 'json_context', None]),
        query=st.text(min_size=0, max_size=200),
        result_ids=st.lists(
            st.integers(min_value=1, max_value=108),
            min_size=0,
            max_size=20,
        ),
    )
    def test_log_ai_search_stores_search_method(self, method, query,
                                                result_ids):
        """_log_ai_search stores the active search_method on the record.

        Feature: json-context-semantic-search, Property 11: Search method is
        logged in AiSearchLog (_log_ai_search constructs the AiSearchLog with
        the active search_method value and persists it via add + commit).

        Validates: Requirements 11.1, 11.2
        """
        # Arrange: capture the constructed AiSearchLog record and mock session.
        fake_record = MagicMock()
        fake_log_cls = MagicMock(return_value=fake_record)
        mock_session = MagicMock()
        results = [{'id': rid} for rid in result_ids]

        # Act: log the search with the parametrized active method.
        with patch.object(sh, 'AiSearchLog', fake_log_cls):
            sh._log_ai_search(
                mock_session, query, results, None, search_method=method
            )

        # Assert: AiSearchLog constructed with search_method=method.
        fake_log_cls.assert_called_once()
        self.assertEqual(
            fake_log_cls.call_args.kwargs['search_method'], method
        )

        # Assert: the constructed record was added and committed.
        mock_session.add.assert_called_once_with(fake_record)
        mock_session.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
