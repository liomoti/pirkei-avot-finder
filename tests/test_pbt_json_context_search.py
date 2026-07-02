"""Property-based tests for the JSON Context Search Lambda.

Covers query-validation properties for json_context_search_handler:
  - Property 1: Invalid queries are rejected with 400
  - Property 2: Queries exceeding 500 characters are rejected
  - Property 3: URL-decoding is applied before validation

Bootstrap pattern (mirrors tests/test_pbt_search_log_results.py):
  - Mock boto3 at module level so the handler's module-level client
    initialization does not require AWS credentials/region.
  - Add the function source directory to sys.path.
  - Import handler functions directly.
"""

import json
import os
import sys
from unittest.mock import MagicMock
from urllib.parse import quote_plus

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

from hypothesis import given, settings, strategies as st  # noqa: E402


# Whitespace characters the handler should treat as "empty" after str.strip().
_WHITESPACE = ' \t\n\r\x0b\x0c'

# Characters that are safe in plain (un-encoded) queries: unquote_plus is the
# identity on text without '%' or '+', so decoded length == raw length.
_PLAIN_ALPHABET = st.characters(
    blacklist_characters='%+' + _WHITESPACE,
    blacklist_categories=('Cs', 'Cc'),
)


def _code_of(response):
    """Extract the error 'code' from a Lambda response body, or None."""
    body = json.loads(response['body'])
    return body.get('code')


# --- Property 1: Invalid queries are rejected with 400 -----------------------

@settings(max_examples=100)
@given(
    whitespace_query=st.text(alphabet=_WHITESPACE, min_size=0, max_size=50)
)
def test_property_1_empty_or_whitespace_query_rejected(whitespace_query):
    """Feature: json-context-semantic-search, Property 1: Invalid queries are rejected with 400

    Validates: Requirements 1.6, 5.1, 5.3

    An empty or whitespace-only query (after URL-decoding and trimming)
    is rejected with statusCode 400 and code VALIDATION_ERROR.
    """
    response = h.handler({'query': whitespace_query}, None)

    assert response['statusCode'] == 400
    assert _code_of(response) == 'VALIDATION_ERROR'


def test_property_1_missing_query_key_rejected():
    """Feature: json-context-semantic-search, Property 1: Invalid queries are rejected with 400

    Validates: Requirements 1.6, 5.1

    A payload missing the 'query' key is rejected with 400 VALIDATION_ERROR.
    """
    response = h.handler({}, None)

    assert response['statusCode'] == 400
    assert _code_of(response) == 'VALIDATION_ERROR'


# --- Property 2: Queries exceeding 500 characters are rejected ---------------

@settings(max_examples=100)
@given(
    long_query=st.text(alphabet=_PLAIN_ALPHABET, min_size=501, max_size=1200)
)
def test_property_2_overlong_query_rejected(long_query):
    """Feature: json-context-semantic-search, Property 2: Queries exceeding 500 characters are rejected

    Validates: Requirements 5.4

    Any query whose decoded length exceeds 500 characters is rejected with
    statusCode 400 and code VALIDATION_ERROR. The alphabet excludes '%', '+'
    and whitespace so the decoded length equals the generated length and the
    query is not first rejected as empty.
    """
    # Guard: generated text is non-empty after trimming and over the limit.
    assert len(long_query) > h.MAX_QUERY_LENGTH

    response = h.handler({'query': long_query}, None)

    assert response['statusCode'] == 400
    assert _code_of(response) == 'VALIDATION_ERROR'


@settings(max_examples=100)
@given(
    ok_query=st.text(alphabet=_PLAIN_ALPHABET, min_size=1, max_size=500)
)
def test_property_2_boundary_query_accepted(ok_query):
    """Feature: json-context-semantic-search, Property 2: Queries exceeding 500 characters are rejected

    Validates: Requirements 5.4

    Complementary boundary: a non-empty query of at most 500 characters is
    NOT rejected for length — _validate_query returns the query with no error.
    """
    query, error = h._validate_query({'query': ok_query})

    assert error is None
    assert query == ok_query.strip()


# --- Property 3: URL-decoding is applied before validation -------------------

@settings(max_examples=100)
@given(space_count=st.integers(min_value=1, max_value=100))
def test_property_3_encoded_spaces_decoded_then_rejected(space_count):
    """Feature: json-context-semantic-search, Property 3: URL-decoding is applied before validation

    Validates: Requirements 5.2

    A query made only of '%20'-encoded spaces decodes to whitespace and is
    therefore rejected as empty. If decoding did NOT happen first, the literal
    '%20...' text would be non-empty and pass validation — so a 400 rejection
    proves decoding occurs before validation.
    """
    encoded = '%20' * space_count

    response = h.handler({'query': encoded}, None)

    assert response['statusCode'] == 400
    assert _code_of(response) == 'VALIDATION_ERROR'


@settings(max_examples=100)
@given(
    hebrew_query=st.text(
        alphabet=st.characters(min_codepoint=0x05D0, max_codepoint=0x05EA),
        min_size=1,
        max_size=100,
    )
)
def test_property_3_encoded_hebrew_decoded_before_validation(hebrew_query):
    """Feature: json-context-semantic-search, Property 3: URL-decoding is applied before validation

    Validates: Requirements 5.2

    URL-encoded Hebrew text is decoded to its original form before validation,
    so the validated query equals the decoded (trimmed) Hebrew string rather
    than the percent-encoded representation.
    """
    encoded = quote_plus(hebrew_query)

    query, error = h._validate_query({'query': encoded})

    assert error is None
    assert query == hebrew_query.strip()


# --- Property 4: All responses conform to the standard envelope format -------

def _assert_valid_envelope(response):
    """Assert a response matches the standard Lambda envelope contract.

    - statusCode is an integer
    - headers is a dict with Content-Type 'application/json' and
      Access-Control-Allow-Origin '*'
    - body is a JSON-serialized string (parses without error)
    """
    # statusCode must be a genuine int (bool is a subclass of int — exclude it)
    assert isinstance(response['statusCode'], int)
    assert not isinstance(response['statusCode'], bool)

    headers = response['headers']
    assert isinstance(headers, dict)
    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'

    # body must be a JSON-serialized string
    assert isinstance(response['body'], str)
    json.loads(response['body'])  # raises if not valid JSON


# Strategy producing a varied mix of input events: valid queries, empty/
# whitespace queries, over-long queries, encoded queries, non-string query
# values, missing 'query' key, and extra unrelated keys.
_event_query_values = st.one_of(
    st.text(alphabet=_PLAIN_ALPHABET, min_size=1, max_size=500),      # valid
    st.text(alphabet=_PLAIN_ALPHABET, min_size=501, max_size=900),    # too long
    st.text(alphabet=_WHITESPACE, min_size=0, max_size=20),           # empty/ws
    st.just('%20%20%20'),                                             # encoded ws
    st.integers(),                                                    # non-string
    st.none(),                                                        # explicit None
    st.booleans(),                                                    # non-string
)


@settings(max_examples=100)
@given(query_value=_event_query_values)
def test_property_4_envelope_for_events_with_query_key(query_value):
    """Feature: json-context-semantic-search, Property 4: All responses conform to the standard envelope format

    Validates: Requirements 1.3, 4.5

    For any event carrying a 'query' key (valid, invalid, empty, over-long,
    encoded, or wrongly typed), the handler response conforms to the standard
    envelope: integer statusCode, headers with Content-Type application/json
    and Access-Control-Allow-Origin '*', and a JSON-string body.
    """
    response = h.handler({'query': query_value}, None)
    _assert_valid_envelope(response)


@settings(max_examples=100)
@given(
    event=st.dictionaries(
        keys=st.text(min_size=1, max_size=10).filter(lambda k: k != 'query'),
        values=st.one_of(st.text(max_size=20), st.integers(), st.none()),
        max_size=4,
    )
)
def test_property_4_envelope_for_events_missing_query_key(event):
    """Feature: json-context-semantic-search, Property 4: All responses conform to the standard envelope format

    Validates: Requirements 1.3, 4.5

    For any event that does NOT contain a 'query' key (including arbitrary
    unrelated keys), the handler still returns a response conforming to the
    standard envelope format.
    """
    response = h.handler(event, None)
    _assert_valid_envelope(response)


def test_property_4_envelope_for_build_response_directly():
    """Feature: json-context-semantic-search, Property 4: All responses conform to the standard envelope format

    Validates: Requirements 1.3, 4.5

    The _build_response helper itself produces a conforming envelope for both
    success and error bodies, since every handler path routes through it.
    """
    _assert_valid_envelope(h._build_response(200, {'results': {}}))
    _assert_valid_envelope(
        h._build_response(500, {'error': 'אירעה שגיאה פנימית', 'code': 'INTERNAL_ERROR'})
    )


# --- LLM response parsing helpers --------------------------------------------

def _make_converse_response(output_text):
    """Build a fake Bedrock Converse response wrapping the given output text.

    Mirrors the shape _parse_llm_response reads from:
    response['output']['message']['content'][0]['text'].
    """
    return {
        'output': {'message': {'content': [{'text': output_text}]}},
        'stopReason': 'end_turn',
    }


def _expected_in_range(entries):
    """Replicate the handler's filter: true ints (not bool) in range 1-108."""
    return [
        n for n in entries
        if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 108
    ]


# Noise text that is safe to place around / outside the JSON object: it must
# not introduce its own braces or backticks that would confuse extraction or
# the markdown-stripping step.
_NOISE_TEXT = st.text(
    alphabet=st.characters(
        blacklist_characters='{}`',
        blacklist_categories=('Cs', 'Cc'),
    ),
    max_size=60,
)

# Entries that may appear inside the relevant_numbers array. A mix of in-range
# integers, out-of-range integers, and non-integer types (floats, strings,
# booleans, None) that must all be discarded except in-range ints. Strings
# exclude backticks so markdown stripping cannot corrupt the embedded JSON.
_ARRAY_ENTRIES = st.one_of(
    st.integers(min_value=1, max_value=108),       # valid, kept
    st.integers(min_value=109, max_value=10_000),  # out of range, dropped
    st.integers(min_value=-10_000, max_value=0),   # out of range, dropped
    st.floats(allow_nan=False, allow_infinity=False),  # non-int, dropped
    st.text(
        alphabet=st.characters(blacklist_characters='`',
                               blacklist_categories=('Cs', 'Cc')),
        max_size=12,
    ),                                             # string, dropped
    st.booleans(),                                 # bool, dropped
    st.none(),                                     # null, dropped
)

# Ways to wrap the JSON object: plain, json-fenced, plainly fenced, or
# surrounded by arbitrary brace-free / backtick-free noise.
_WRAP_MODE = st.sampled_from(['plain', 'json_fence', 'plain_fence', 'surrounded'])


# --- Property 6: LLM response parsing correctly extracts valid numbers -------

@settings(max_examples=100)
@given(
    entries=st.lists(_ARRAY_ENTRIES, max_size=30),
    wrap=_WRAP_MODE,
    prefix=_NOISE_TEXT,
    suffix=_NOISE_TEXT,
)
def test_property_6_parsing_extracts_valid_numbers(entries, wrap, prefix, suffix):
    """Feature: json-context-semantic-search, Property 6: LLM response parsing correctly extracts valid numbers

    Validates: Requirements 9.1, 9.2, 9.4

    For any LLM output containing a valid JSON object with a relevant_numbers
    array (optionally wrapped in markdown fences and surrounded by arbitrary
    text), the parser extracts exactly the integers in range 1-108 in order,
    discarding all non-integer or out-of-range entries.
    """
    json_str = json.dumps({'relevant_numbers': entries}, ensure_ascii=False)

    if wrap == 'json_fence':
        output_text = f'```json\n{json_str}\n```'
    elif wrap == 'plain_fence':
        output_text = f'```\n{json_str}\n```'
    elif wrap == 'surrounded':
        output_text = f'{prefix}\n{json_str}\n{suffix}'
    else:
        output_text = json_str

    response = _make_converse_response(output_text)
    result = h._parse_llm_response(response)

    assert result == _expected_in_range(entries)


# --- Property 7: Unparseable LLM output yields empty results -----------------

# LLM outputs that the parser must reject, returning an empty result list:
#   - empty / whitespace-only text (no JSON at all)
#   - text containing no '{' character
#   - text whose braces enclose content that is not valid JSON
_UNPARSEABLE_OUTPUT = st.one_of(
    st.just(''),
    st.text(alphabet=_WHITESPACE, min_size=0, max_size=30),
    # No '{' anywhere — extraction finds no JSON object start.
    st.text(
        alphabet=st.characters(blacklist_characters='{',
                               blacklist_categories=('Cs', 'Cc')),
        max_size=80,
    ),
    # Braces present but the enclosed text is not valid JSON.
    st.sampled_from([
        '{not json}',
        '{"relevant_numbers": [1, 2, }',
        '{ "x" "y" }',
        '{,}',
        '{"k":}',
        '{"relevant_numbers" [1,2,3]}',
        'noise {==} more noise',
    ]),
)


@settings(max_examples=100)
@given(output_text=_UNPARSEABLE_OUTPUT)
def test_property_7_unparseable_output_yields_empty(output_text):
    """Feature: json-context-semantic-search, Property 7: Unparseable LLM output yields empty results

    Validates: Requirements 4.4, 9.3, 9.5, 9.6

    For any LLM output that is empty, contains no '{', or whose first-'{'..last-'}'
    span is not valid JSON, the parser returns an empty result list.
    """
    response = _make_converse_response(output_text)
    result = h._parse_llm_response(response)

    assert result == []


def test_property_7_missing_relevant_numbers_key_yields_empty():
    """Feature: json-context-semantic-search, Property 7: Unparseable LLM output yields empty results

    Validates: Requirements 9.5

    Valid JSON that lacks the 'relevant_numbers' key yields an empty result.
    """
    response = _make_converse_response('{"other_key": [1, 2, 3]}')
    assert h._parse_llm_response(response) == []


# --- Property 5: Relevance scores are correctly computed ---------------------

import math  # noqa: E402


@settings(max_examples=100)
@given(
    numbers=st.lists(
        st.integers(min_value=1, max_value=108),
        min_size=1,
        max_size=20,
        unique=True,
    )
)
def test_property_5_relevance_scores_correctly_computed(numbers):
    """Feature: json-context-semantic-search, Property 5: Relevance scores are correctly computed

    Validates: Requirements 4.1, 4.2

    For any list of N relevant mishna numbers (1 <= N <= 20), _build_results
    produces a dict where keys are the string forms of the numbers, the first
    number maps to exactly 1.0, the i-th number maps to 1.0 - i*(1.0/N), and
    every score is non-negative.
    """
    n = len(numbers)
    results = h._build_results(numbers)

    # Keys are the string representations of the input numbers, in order.
    assert list(results.keys()) == [str(num) for num in numbers]

    # First item always scores exactly 1.0.
    assert results[str(numbers[0])] == 1.0

    step = 1.0 / n
    for i, num in enumerate(numbers):
        score = results[str(num)]
        # i-th score equals 1.0 - i*(1.0/N) (float-tolerant comparison).
        assert math.isclose(score, 1.0 - i * step, rel_tol=1e-9, abs_tol=1e-12)
        # All scores are non-negative.
        assert score >= 0
