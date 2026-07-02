"""Property-based tests for _get_search_log_results() in admin_handler.

Uses hypothesis to validate correctness properties from the design document.
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

from admin_handler import _get_search_log_results  # noqa: E402

from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Hebrew letters used for chapter/mishna identifiers (the 6 chapters)
_hebrew_letters = ['א', 'ב', 'ג', 'ד', 'ה', 'ו']

# Strategy: unique list of (chapter, mishna) tuples → Mishna IDs like "א_ב"
mishna_id_tuples = st.lists(
    st.tuples(
        st.sampled_from(_hebrew_letters),
        st.sampled_from(_hebrew_letters),
    ),
    min_size=1,
    max_size=10,
    unique=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_mishna(mid, chapter, mishna_num):
    """Create a mock Mishna object with deterministic text_pretty."""
    m = MagicMock()
    m.id = mid
    m.chapter = chapter
    m.mishna = mishna_num
    m.text_pretty = f'טקסט עבור {mid}'
    return m


def _make_mock_log_entry(log_id, query_text, result_ids_csv):
    """Create a mock AiSearchLog object."""
    log = MagicMock()
    log.id = log_id
    log.query_text = query_text
    log.result_ids = result_ids_csv
    return log


def _build_session_mock(log_entry, mishna_records):
    """Build a mock session that returns the given log entry and mishna records.

    The session.query() mock dispatches based on call order:
    first call → AiSearchLog query, second call → Mishna query.
    """
    session = MagicMock()
    call_count = {'n': 0}

    def query_side_effect(model):
        call_count['n'] += 1
        q = MagicMock()
        if call_count['n'] == 1:
            # AiSearchLog query
            q.filter_by.return_value.first.return_value = log_entry
        else:
            # Mishna query
            q.filter.return_value.all.return_value = mishna_records
        return q

    session.query.side_effect = query_side_effect
    return session


# ---------------------------------------------------------------------------
# Property 1: Result ID resolution preserves order and content
# Validates: Requirements 2.3, 2.6
# ---------------------------------------------------------------------------

class TestPropertyOrderAndContent(unittest.TestCase):
    """Property 1: Result ID resolution preserves order and content.

    **Validates: Requirements 2.3, 2.6**

    For any valid result_ids CSV string containing Mishna IDs that exist in
    the database, the handler SHALL return exactly those Mishna objects in the
    same order as they appear in the CSV, and each returned object SHALL
    contain the fields id, chapter, mishna, and text_pretty matching the
    corresponding database record.
    """

    @given(id_tuples=mishna_id_tuples)
    @settings(max_examples=100)
    def test_results_preserve_order_and_content(self, id_tuples):
        """Generated Mishna IDs are returned in CSV order with correct fields."""
        # Build IDs and mock Mishna records from generated tuples
        mishna_ids = [f'{ch}_{mi}' for ch, mi in id_tuples]
        mishna_records = [
            _make_mock_mishna(mid, ch, mi)
            for (ch, mi), mid in zip(id_tuples, mishna_ids)
        ]

        result_ids_csv = ','.join(mishna_ids)
        log_entry = _make_mock_log_entry(1, 'שאילתה כלשהי', result_ids_csv)

        session = _build_session_mock(log_entry, mishna_records)

        # Act
        response = _get_search_log_results(session, '1')

        # Assert
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])

        self.assertEqual(body['query_text'], 'שאילתה כלשהי')
        self.assertEqual(len(body['results']), len(mishna_ids))

        for i, (expected_id, (ch, mi)) in enumerate(zip(mishna_ids, id_tuples)):
            result = body['results'][i]
            self.assertEqual(result['id'], expected_id)
            self.assertEqual(result['chapter'], ch)
            self.assertEqual(result['mishna'], mi)
            self.assertEqual(result['text_pretty'], f'טקסט עבור {expected_id}')


# ---------------------------------------------------------------------------
# Property 2: Empty or NULL result_ids yields empty results
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

class TestPropertyEmptyResultIds(unittest.TestCase):
    """Property 2: Empty or NULL result_ids yields empty results.

    **Validates: Requirements 2.4**

    For any log entry where result_ids is NULL, empty string, or contains
    only whitespace/commas, the handler SHALL return an empty results list
    with HTTP 200 and the correct query_text.
    """

    @given(
        query_text=st.text(min_size=1, max_size=50),
        result_ids=st.sampled_from([None, '', '  ', ',,', ', ,', '  ,  ']),
    )
    @settings(max_examples=100)
    def test_empty_or_null_result_ids_yields_empty_results(self, query_text, result_ids):
        """Any NULL/empty/whitespace-only result_ids returns 200 with empty results."""
        log_entry = _make_mock_log_entry(1, query_text, result_ids)

        # For empty/NULL result_ids, the handler only queries AiSearchLog (no Mishna query)
        session = MagicMock()
        call_count = {'n': 0}

        def query_side_effect(model):
            call_count['n'] += 1
            q = MagicMock()
            if call_count['n'] == 1:
                # AiSearchLog query
                q.filter_by.return_value.first.return_value = log_entry
            else:
                # Mishna query — should not be reached for empty result_ids
                q.filter.return_value.all.return_value = []
            return q

        session.query.side_effect = query_side_effect

        # Act
        response = _get_search_log_results(session, '1')

        # Assert
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])

        self.assertEqual(body['query_text'], query_text)
        self.assertIsInstance(body['results'], list)
        self.assertEqual(len(body['results']), 0)


# ---------------------------------------------------------------------------
# Property 3: Missing Mishna IDs are silently skipped
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

class TestPropertyMissingIdsSkipped(unittest.TestCase):
    """Property 3: Missing Mishna IDs are silently skipped.

    **Validates: Requirements 2.3**

    For any result_ids CSV string containing a mix of existing and
    non-existing Mishna IDs, the handler SHALL return only the Mishna
    objects for IDs that exist in the database, preserving their relative
    order from the original CSV, without raising an error.
    """

    @given(
        existing_tuples=st.lists(
            st.tuples(
                st.sampled_from(_hebrew_letters),
                st.sampled_from(_hebrew_letters),
            ),
            min_size=1,
            max_size=6,
            unique=True,
        ),
        missing_tuples=st.lists(
            st.tuples(
                st.sampled_from(['ז', 'ח', 'ט', 'י', 'כ', 'ל']),
                st.sampled_from(['ז', 'ח', 'ט', 'י', 'כ', 'ל']),
            ),
            min_size=1,
            max_size=6,
            unique=True,
        ),
        seed=st.randoms(use_true_random=False),
    )
    @settings(max_examples=100)
    def test_missing_ids_are_silently_skipped(self, existing_tuples, missing_tuples, seed):
        """Only existing Mishna IDs appear in results; missing ones are skipped."""
        # Build existing IDs and their mock Mishna records
        existing_ids = [f'{ch}_{mi}' for ch, mi in existing_tuples]
        mishna_records = [
            _make_mock_mishna(mid, ch, mi)
            for (ch, mi), mid in zip(existing_tuples, existing_ids)
        ]

        # Build missing IDs (no corresponding Mishna records)
        missing_ids = [f'{ch}_{mi}' for ch, mi in missing_tuples]

        # Interleave existing and missing IDs randomly
        all_ids = existing_ids + missing_ids
        seed.shuffle(all_ids)

        result_ids_csv = ','.join(all_ids)
        log_entry = _make_mock_log_entry(1, 'שאילתה כלשהי', result_ids_csv)

        # Session mock returns Mishna records only for existing IDs
        session = _build_session_mock(log_entry, mishna_records)

        # Act
        response = _get_search_log_results(session, '1')

        # Assert — response is 200
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])

        # Assert — results contain only existing IDs
        returned_ids = [r['id'] for r in body['results']]
        self.assertEqual(set(returned_ids), set(existing_ids))

        # Assert — results preserve relative order from the CSV
        # Extract the order of existing IDs as they appeared in the shuffled list
        expected_order = [mid for mid in all_ids if mid in set(existing_ids)]
        self.assertEqual(returned_ids, expected_order)

        # Assert — each result has correct fields
        existing_map = {mid: (ch, mi) for (ch, mi), mid in zip(existing_tuples, existing_ids)}
        for result in body['results']:
            ch, mi = existing_map[result['id']]
            self.assertEqual(result['chapter'], ch)
            self.assertEqual(result['mishna'], mi)
            self.assertEqual(result['text_pretty'], f'טקסט עבור {result["id"]}')


if __name__ == '__main__':
    unittest.main()
