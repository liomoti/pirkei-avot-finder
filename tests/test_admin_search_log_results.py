"""Unit tests for _get_search_log_results() in admin_handler.

Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.6
"""

import json
import sys
import os
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Bootstrap: mock heavy third-party / environment-dependent modules that
# cannot be imported in the test environment, then add paths so
# admin_handler can be imported from source.
# ---------------------------------------------------------------------------

# 1. Add SharedLayer python dir so sqlalchemy, models, response, text_utils resolve
_layer_python = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '.aws-sam', 'build', 'SharedLayer', 'python')
)
if _layer_python not in sys.path:
    sys.path.insert(0, _layer_python)

# 2. Mock boto3 (not installed locally — only available in Lambda runtime)
sys.modules.setdefault('boto3', MagicMock())

# 3. Mock the db module so it doesn't try to read DATABASE_URL or create a real engine
_db_mock = types.ModuleType('db')
_db_mock.Session = MagicMock()
sys.modules['db'] = _db_mock

# 4. Add source functions/admin/ dir so we import the latest admin_handler
_admin_src = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'functions', 'admin')
)
if _admin_src not in sys.path:
    sys.path.insert(0, _admin_src)

from admin_handler import _get_search_log_results, handler  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(path, method='GET', role='admin'):
    """Build a minimal API Gateway v2 event dict."""
    return {
        'rawPath': path,
        'requestContext': {
            'http': {'method': method},
            'authorizer': {
                'jwt': {
                    'claims': {'custom:role': role}
                }
            }
        }
    }


def _make_log_entry(log_id=1, query_text='מהי חכמה', result_ids='א_א,ב_ג', result_count=2):
    """Create a mock AiSearchLog object."""
    log = MagicMock()
    log.id = log_id
    log.query_text = query_text
    log.result_ids = result_ids
    log.result_count = result_count
    return log


def _make_mishna(mid, chapter, mishna_num, text_pretty):
    """Create a mock Mishna object."""
    m = MagicMock()
    m.id = mid
    m.chapter = chapter
    m.mishna = mishna_num
    m.text_pretty = text_pretty
    return m


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestAdminRoleCheck(unittest.TestCase):
    """Test that the handler route enforces admin role."""

    def test_non_admin_returns_403(self):
        """Validates: Requirement 2.2 — non-admin callers get 403."""
        with unittest.mock.patch('admin_handler.Session') as mock_session_cls:
            mock_session_cls.return_value = MagicMock()

            event = _make_event('/api/admin/search-logs/1/results', role='user')
            result = handler(event, None)

        self.assertEqual(result['statusCode'], 403)
        body = json.loads(result['body'])
        self.assertEqual(body['code'], 'FORBIDDEN')


class TestInvalidLogId(unittest.TestCase):
    """Test validation of the log_id parameter."""

    def test_non_integer_log_id_returns_400(self):
        """Validates: Requirement 2.3 — invalid log_id returns 400."""
        session = MagicMock()
        result = _get_search_log_results(session, 'abc')

        self.assertEqual(result['statusCode'], 400)
        body = json.loads(result['body'])
        self.assertEqual(body['code'], 'VALIDATION_ERROR')
        self.assertIn('מזהה לוג לא חוקי', body['error'])


class TestNonExistentLogId(unittest.TestCase):
    """Test behaviour when the log entry does not exist."""

    def test_missing_log_returns_404(self):
        """Validates: Requirement 2.5 — non-existent log_id returns 404."""
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None

        result = _get_search_log_results(session, '999')

        self.assertEqual(result['statusCode'], 404)
        body = json.loads(result['body'])
        self.assertEqual(body['code'], 'NOT_FOUND')
        self.assertIn('רשומת לוג לא נמצאה', body['error'])


class TestNullResultIds(unittest.TestCase):
    """Test that NULL result_ids returns an empty results list."""

    def test_null_result_ids_returns_empty_list(self):
        """Validates: Requirement 2.4 — NULL result_ids yields empty results with 200."""
        session = MagicMock()
        log_entry = _make_log_entry(result_ids=None)
        session.query.return_value.filter_by.return_value.first.return_value = log_entry

        result = _get_search_log_results(session, '1')

        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['results'], [])
        self.assertEqual(body['query_text'], 'מהי חכמה')


class TestEmptyStringResultIds(unittest.TestCase):
    """Test that empty-string result_ids returns an empty results list."""

    def test_empty_string_result_ids_returns_empty_list(self):
        """Validates: Requirement 2.4 — empty string result_ids yields empty results with 200."""
        session = MagicMock()
        log_entry = _make_log_entry(result_ids='')
        session.query.return_value.filter_by.return_value.first.return_value = log_entry

        result = _get_search_log_results(session, '1')

        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['results'], [])
        self.assertEqual(body['query_text'], 'מהי חכמה')


class TestSuccessfulResponseShape(unittest.TestCase):
    """Test the shape and content of a successful response."""

    def test_response_contains_query_text_and_results(self):
        """Validates: Requirements 2.3, 2.6 — response has query_text and results with correct fields."""
        session = MagicMock()

        log_entry = _make_log_entry(result_ids='א_א,א_ב')
        m1 = _make_mishna('א_א', 'א', 'א', 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי')
        m2 = _make_mishna('א_ב', 'א', 'ב', 'שִׁמְעוֹן הַצַּדִּיק')

        call_count = {'n': 0}

        def side_effect(model):
            call_count['n'] += 1
            q = MagicMock()
            if call_count['n'] == 1:
                # AiSearchLog query
                q.filter_by.return_value.first.return_value = log_entry
            else:
                # Mishna query
                q.filter.return_value.all.return_value = [m1, m2]
            return q

        session.query.side_effect = side_effect

        result = _get_search_log_results(session, '1')

        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])

        # Top-level keys
        self.assertIn('query_text', body)
        self.assertIn('results', body)
        self.assertEqual(body['query_text'], 'מהי חכמה')

        # Results array
        self.assertEqual(len(body['results']), 2)

        # Each result has the required fields
        for r in body['results']:
            self.assertIn('id', r)
            self.assertIn('chapter', r)
            self.assertIn('mishna', r)
            self.assertIn('text_pretty', r)

        # Verify first result values
        self.assertEqual(body['results'][0]['id'], 'א_א')
        self.assertEqual(body['results'][0]['chapter'], 'א')
        self.assertEqual(body['results'][0]['mishna'], 'א')
        self.assertEqual(body['results'][0]['text_pretty'], 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי')


class TestResultsPreserveOrder(unittest.TestCase):
    """Test that results are returned in the same order as result_ids."""

    def test_order_matches_result_ids(self):
        """Validates: Requirements 2.3, 2.6 — results preserve the order from result_ids."""
        session = MagicMock()

        # result_ids in a specific order: ב_ג first, then א_א
        log_entry = _make_log_entry(result_ids='ב_ג,א_א')
        m1 = _make_mishna('א_א', 'א', 'א', 'טקסט א')
        m2 = _make_mishna('ב_ג', 'ב', 'ג', 'טקסט ב')

        call_count = {'n': 0}

        def side_effect(model):
            call_count['n'] += 1
            q = MagicMock()
            if call_count['n'] == 1:
                q.filter_by.return_value.first.return_value = log_entry
            else:
                # Return in DB order (different from result_ids order)
                q.filter.return_value.all.return_value = [m1, m2]
            return q

        session.query.side_effect = side_effect

        result = _get_search_log_results(session, '1')

        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])

        # ב_ג should come first (matching result_ids order), not DB order
        self.assertEqual(body['results'][0]['id'], 'ב_ג')
        self.assertEqual(body['results'][1]['id'], 'א_א')


if __name__ == '__main__':
    unittest.main()
