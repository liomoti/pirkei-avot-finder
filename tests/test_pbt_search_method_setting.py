"""Property-based tests for the semantic_search_method SiteSetting default.

Covers:
  - Property 9: Setting default is rag when key is absent

Bootstrap pattern (mirrors tests/test_pbt_json_context_search.py):
  - Mock boto3 at module level so importing the shared layer does not require
    AWS credentials/region.
  - Add the shared layer source directory to sys.path.
  - Import the model helpers directly.
"""

import os
import sys
from unittest.mock import MagicMock

# --- Bootstrap: mock boto3 before importing the shared layer modules ---------
sys.modules['boto3'] = MagicMock()

# Add the shared layer source directory to sys.path
_SHARED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'layers', 'shared'
)
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

import models as m  # noqa: E402

from hypothesis import given, settings, strategies as st  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def _make_mock_session():
    """Build a mock SQLAlchemy session whose
    query(...).filter_by(...).first() chain returns None — simulating a
    SiteSetting table with no 'semantic_search_method' row.
    """
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session


# --- Property 9: Setting default is rag when key is absent -------------------

@settings(max_examples=100)
@given(
    # Arbitrary set of unrelated keys present in the table — none of which is
    # 'semantic_search_method'. The absence of the target key is what matters.
    absent_keys=st.lists(
        st.text(min_size=0, max_size=40).filter(
            lambda k: k != 'semantic_search_method'
        ),
        max_size=10,
    )
)
def test_property_9_default_is_rag_when_key_absent_mock(absent_keys):
    """Feature: json-context-semantic-search, Property 9: Setting default is rag when key is absent

    Validates: Requirements 10.1

    For any database state in which the 'semantic_search_method' key does not
    exist (modeled by the query chain returning None), get_semantic_search_method
    returns 'rag'.
    """
    session = _make_mock_session()

    result = m.get_semantic_search_method(session)

    assert result == 'rag'
    # The lookup must target the correct setting key.
    session.query.return_value.filter_by.assert_called_with(
        key='semantic_search_method'
    )


@settings(max_examples=100)
@given(
    # Populate the in-memory table with arbitrary SiteSetting rows that never
    # include the 'semantic_search_method' key, to exercise a real query path.
    other_settings=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=40).filter(
                lambda k: k != 'semantic_search_method'
            ),
            st.text(min_size=0, max_size=40),
        ),
        max_size=8,
    )
)
def test_property_9_default_is_rag_when_key_absent_sqlite(other_settings):
    """Feature: json-context-semantic-search, Property 9: Setting default is rag when key is absent

    Validates: Requirements 10.1

    Using a real in-memory SQLite SiteSetting table seeded with unrelated keys
    (but never 'semantic_search_method'), get_semantic_search_method returns
    'rag' because the target key is absent.
    """
    engine = create_engine('sqlite:///:memory:')
    m.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Deduplicate keys to respect the primary-key constraint.
        seen = set()
        for key, value in other_settings:
            if key in seen:
                continue
            seen.add(key)
            session.add(m.SiteSetting(key=key, value=value))
        session.commit()

        result = m.get_semantic_search_method(session)

        assert result == 'rag'
    finally:
        session.close()
        engine.dispose()


# ===========================================================================
# Property 8: Setting value validation accepts only allowed values
# ===========================================================================
#
# Bootstrap for importing the Settings Handler:
#   - The handler imports `from db import Session`, `from models import ...`,
#     and `from response import ...`. db.py eagerly builds a SQLAlchemy engine
#     from the DATABASE_URL env var, which is not available locally, so we mock
#     the `db` module before importing the handler.
#   - Add functions/settings and layers/shared to sys.path so the handler's
#     bare imports resolve.

import json  # noqa: E402
from unittest.mock import patch  # noqa: E402

# Mock the `db` module so importing settings_handler does not require a real
# database engine / DATABASE_URL.
_mock_db = MagicMock()
sys.modules['db'] = _mock_db

# Add the settings function source directory to sys.path.
_SETTINGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'functions', 'settings'
)
if _SETTINGS_DIR not in sys.path:
    sys.path.insert(0, _SETTINGS_DIR)

import settings_handler as sh  # noqa: E402


# Values that the endpoint must accept and persist.
_ALLOWED_METHODS = ('rag', 'json_context')


@settings(max_examples=100)
@given(method=st.one_of(st.sampled_from(_ALLOWED_METHODS), st.text(max_size=40)))
def test_property_8_setting_value_validation(method):
    """Feature: json-context-semantic-search, Property 8: Setting value validation accepts only allowed values

    Validates: Requirements 10.3, 10.4

    For any string value submitted to PUT /api/settings/semantic-search-method,
    the endpoint persists it (calls set_semantic_search_method) and returns a
    success response if and only if the value is exactly 'rag' or 'json_context'.
    Any other string yields a 400 VALIDATION_ERROR and does NOT persist.
    """
    session = MagicMock()
    event = {'body': json.dumps({'method': method})}

    # Patch the module-level set_semantic_search_method so we can assert whether
    # persistence happened, without touching a real DB.
    with patch.object(sh, 'set_semantic_search_method') as mock_set:
        response = sh._update_semantic_search_method(session, event)

    body = json.loads(response['body'])

    if method in _ALLOWED_METHODS:
        # Persisted exactly once with the submitted value.
        mock_set.assert_called_once_with(session, method)
        assert response['statusCode'] == 200
        assert body.get('semantic_search_method') == method
    else:
        # Rejected with 400 VALIDATION_ERROR and never persisted.
        mock_set.assert_not_called()
        assert response['statusCode'] == 400
        assert body.get('code') == 'VALIDATION_ERROR'
