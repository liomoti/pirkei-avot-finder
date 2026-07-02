"""Property-based tests for serialize_search_log search_method serialization.

Covers:
  - Property 12: serialize_search_log includes search_method field

Bootstrap pattern (mirrors tests/test_pbt_search_method_setting.py):
  - Mock boto3 at module level so importing the shared layer does not require
    AWS credentials/region.
  - Add the shared layer source directory to sys.path.
  - Import the response helpers directly.
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

# --- Bootstrap: mock boto3 before importing the shared layer modules ---------
sys.modules['boto3'] = MagicMock()

# Add the shared layer source directory to sys.path.
_SHARED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'layers', 'shared'
)
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

import response as r  # noqa: E402

from hypothesis import given, settings, strategies as st  # noqa: E402


def _make_fake_log(search_method, created_at):
    """Build a fake AiSearchLog-like object with the attributes that
    serialize_search_log reads. Uses a MagicMock with explicit attributes so
    no real ORM/database is involved.
    """
    log = MagicMock()
    log.id = 1
    log.query_text = 'מה אומרים על ענווה?'
    log.result_count = 3
    log.result_ids = '3,15,42'
    log.user_sub = 'sub-123'
    log.search_method = search_method
    log.created_at = created_at
    return log


# --- Property 12: serialize_search_log includes search_method field ----------

@settings(max_examples=100)
@given(
    search_method=st.sampled_from(['rag', 'json_context', None]),
    created_at=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
    ),
)
def test_property_12_serialize_includes_search_method(search_method, created_at):
    """Feature: json-context-semantic-search, Property 12: serialize_search_log includes search_method field

    Validates: Requirements 11.3

    For any AiSearchLog record whose search_method is 'rag', 'json_context', or
    None, serialize_search_log returns a dict that contains a 'search_method'
    key equal to the record's value.
    """
    log = _make_fake_log(search_method, created_at)

    result = r.serialize_search_log(log)

    assert 'search_method' in result
    assert result['search_method'] == search_method
