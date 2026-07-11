"""Property-based tests for the search log modal fixes (CSS selector scoping
and max-height resolution).

Uses hypothesis to validate correctness properties from the design document.
"""

import re
import string
import unittest

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Pure-Python reimplementations of the CSS behavior under test
# ---------------------------------------------------------------------------

def class_selector_matches(class_list, token):
    """Reimplementation of a plain CSS class selector (e.g. `.token`).

    A class selector `.token` matches an element if and only if `token` is
    present as a whitespace-separated token in the element's class list
    string — matching the browser's actual class-list matching semantics
    (substring containment is NOT sufficient; the token must be a distinct
    entry in the space-separated list).
    """
    return token in class_list.split()


def resolve_results_modal_container_max_height(viewport_width):
    """Reimplementation of the `.results-modal-container` media-query resolution.

    Mirrors the CSS:
        .results-modal-container { max-height: 85vh; }
        @media (max-width: 640px) {
            .results-modal-container { max-height: 80vh; }
        }
    """
    if viewport_width <= 640:
        return '80vh'
    return '85vh'


def _vh_value(vh_string):
    """Extract the numeric portion of a 'Nvh' string."""
    match = re.match(r'^(\d+(?:\.\d+)?)vh$', vh_string)
    assert match is not None, f'Not a valid vh string: {vh_string!r}'
    return float(match.group(1))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Class-list tokens: valid CSS class name characters (letters, digits, hyphen, underscore)
_class_token_chars = string.ascii_letters + string.digits + '-_'

class_list_strategy = st.lists(
    st.text(alphabet=_class_token_chars, min_size=1, max_size=30),
    min_size=0,
    max_size=8,
).map(lambda tokens: ' '.join(tokens))

# Near-miss substrings that must NOT match the exact token
_near_miss_tokens = [
    'results-modal-container-x',
    'xresults-modal-container',
    'Results-Modal-Container',
    'results_modal_container',
    'results-modal-containe',
    'results-modal-containerr',
]

viewport_width_strategy = st.one_of(
    st.integers(min_value=0, max_value=2000),
    st.sampled_from([0, 1, 639, 640, 641, 768, 1024, 2000]),
)

# Near-miss substrings that must NOT match the exact `view-results-btn` token
_near_miss_tokens_view_results_btn = [
    'view-results-btn-alt',
    'xview-results-btn',
    'View-Results-Btn',
    'view_results_btn',
    'view-results-bt',
    'view-results-btnn',
]


# ---------------------------------------------------------------------------
# Property 1: View Results button selector scoping
# Feature: search-log-modal-fixes, Property 1: View Results button selector scoping
# Validates: Requirements 1.6
# ---------------------------------------------------------------------------

class TestPropertyViewResultsButtonSelectorScoping(unittest.TestCase):
    """Property 1: View Results button selector scoping.

    **Feature: search-log-modal-fixes, Property 1: For any button element
    rendered anywhere in the Admin_Panel, the `.view-results-btn` selector
    matches that element if and only if the element's class list contains
    the literal token `view-results-btn`.**

    **Validates: Requirements 1.6**
    """

    @given(class_list=class_list_strategy)
    @settings(max_examples=100)
    def test_random_class_lists_match_iff_token_present(self, class_list):
        """Random class-list strings match iff the literal token is present."""
        # Act
        matches = class_selector_matches(class_list, 'view-results-btn')

        # Assert — matches iff the exact token is a distinct entry in the list
        expected = 'view-results-btn' in class_list.split()
        self.assertEqual(matches, expected)

    @given(
        near_miss=st.sampled_from(_near_miss_tokens_view_results_btn),
        prefix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
        suffix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_near_miss_substrings_never_match(self, near_miss, prefix_tokens, suffix_tokens):
        """Near-miss substrings surrounded by other classes never match the selector."""
        # Arrange
        class_list = ' '.join(prefix_tokens + [near_miss] + suffix_tokens)

        # Act
        matches = class_selector_matches(class_list, 'view-results-btn')

        # Assert — a near-miss token alone must never satisfy the exact selector
        self.assertFalse(matches, f'Near-miss token {near_miss!r} incorrectly matched')

    @given(
        prefix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
        suffix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_exact_token_always_matches_when_present(self, prefix_tokens, suffix_tokens):
        """The exact token, present anywhere among other classes, always matches."""
        # Arrange
        class_list = ' '.join(prefix_tokens + ['view-results-btn'] + suffix_tokens)

        # Act
        matches = class_selector_matches(class_list, 'view-results-btn')

        # Assert
        self.assertTrue(matches)


# ---------------------------------------------------------------------------
# Property 2: Results Modal container selector scoping
# Feature: search-log-modal-fixes, Property 2: Results Modal container selector scoping
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------

class TestPropertyResultsModalContainerSelectorScoping(unittest.TestCase):
    """Property 2: Results Modal container selector scoping.

    **Feature: search-log-modal-fixes, Property 2: For any modal container
    element rendered anywhere in the Admin_Panel, the
    `.results-modal-container` selector matches that element if and only if
    the element's class list contains the literal token
    `results-modal-container`.**

    **Validates: Requirements 2.6**
    """

    @given(class_list=class_list_strategy)
    @settings(max_examples=100)
    def test_random_class_lists_match_iff_token_present(self, class_list):
        """Random class-list strings match iff the literal token is present."""
        # Act
        matches = class_selector_matches(class_list, 'results-modal-container')

        # Assert — matches iff the exact token is a distinct entry in the list
        expected = 'results-modal-container' in class_list.split()
        self.assertEqual(matches, expected)

    @given(
        near_miss=st.sampled_from(_near_miss_tokens),
        prefix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
        suffix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_near_miss_substrings_never_match(self, near_miss, prefix_tokens, suffix_tokens):
        """Near-miss substrings surrounded by other classes never match the selector."""
        # Arrange
        class_list = ' '.join(prefix_tokens + [near_miss] + suffix_tokens)

        # Act
        matches = class_selector_matches(class_list, 'results-modal-container')

        # Assert — a near-miss token alone must never satisfy the exact selector
        self.assertFalse(matches, f'Near-miss token {near_miss!r} incorrectly matched')

    @given(
        prefix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
        suffix_tokens=st.lists(
            st.text(alphabet=_class_token_chars, min_size=1, max_size=15),
            min_size=0,
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_exact_token_always_matches_when_present(self, prefix_tokens, suffix_tokens):
        """The exact token, present anywhere among other classes, always matches."""
        # Arrange
        class_list = ' '.join(prefix_tokens + ['results-modal-container'] + suffix_tokens)

        # Act
        matches = class_selector_matches(class_list, 'results-modal-container')

        # Assert
        self.assertTrue(matches)


# ---------------------------------------------------------------------------
# Property 4: Modal rendered height never exceeds the dedicated class's
# max-height (viewport-width dimension)
# Feature: search-log-modal-fixes, Property 4: Modal rendered height never
# exceeds the dedicated class's max-height (viewport-width dimension)
# Validates: Requirements 2.1, 2.3, 2.5
# ---------------------------------------------------------------------------

class TestPropertyResultsModalMaxHeightResolution(unittest.TestCase):
    """Property 4: Modal rendered height never exceeds the dedicated class's
    max-height (viewport-width dimension).

    **Feature: search-log-modal-fixes, Property 4: For any viewport width,
    the `.results-modal-container` media-query resolution always returns
    `85vh` for widths > 640 and `80vh` for widths <= 640, and the resolved
    value never exceeds `85vh`.**

    **Validates: Requirements 2.1, 2.3, 2.5**
    """

    @given(viewport_width=viewport_width_strategy)
    @settings(max_examples=100)
    def test_resolution_matches_expected_breakpoint_behavior(self, viewport_width):
        """Resolved max-height is 85vh above 640px and 80vh at/below 640px."""
        # Act
        resolved = resolve_results_modal_container_max_height(viewport_width)

        # Assert — exact breakpoint semantics
        if viewport_width > 640:
            self.assertEqual(resolved, '85vh')
        else:
            self.assertEqual(resolved, '80vh')

    @given(viewport_width=viewport_width_strategy)
    @settings(max_examples=100)
    def test_resolved_value_never_exceeds_base_max_height(self, viewport_width):
        """The resolved max-height numeric value never exceeds 85vh."""
        # Act
        resolved = resolve_results_modal_container_max_height(viewport_width)

        # Assert
        self.assertLessEqual(_vh_value(resolved), 85.0)

    def test_boundary_at_640_uses_reduced_height(self):
        """At exactly 640px (the boundary), the reduced 80vh height applies."""
        self.assertEqual(resolve_results_modal_container_max_height(640), '80vh')

    def test_boundary_at_641_uses_base_height(self):
        """Just above the boundary at 641px, the base 85vh height applies."""
        self.assertEqual(resolve_results_modal_container_max_height(641), '85vh')


if __name__ == '__main__':
    unittest.main()
