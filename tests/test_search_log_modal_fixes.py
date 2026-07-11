"""Unit tests for the search log modal fixes (button contrast + modal scroll).

Validates: Requirements 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.3
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_CSS_PATH = os.path.join(REPO_ROOT, 'frontend', 'static', 'style.css')
MANAGE_HTML_PATH = os.path.join(REPO_ROOT, 'frontend', 'manage.html')


def _read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _hex_to_rgb(hex_color):
    """Convert a '#rrggbb' string to an (r, g, b) tuple of ints."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _composite_over_white(rgb, alpha):
    """Composite an RGB color with the given alpha over a white background."""
    r, g, b = rgb
    return (
        r * alpha + 255 * (1 - alpha),
        g * alpha + 255 * (1 - alpha),
        b * alpha + 255 * (1 - alpha),
    )


def _relative_luminance(rgb):
    """Compute WCAG relative luminance for an (r, g, b) tuple (0-255 channels)."""
    def channel_luminance(c):
        c_srgb = c / 255.0
        if c_srgb <= 0.03928:
            return c_srgb / 12.92
        return ((c_srgb + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    r_lin, g_lin, b_lin = channel_luminance(r), channel_luminance(g), channel_luminance(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _contrast_ratio(rgb1, rgb2):
    """Compute the WCAG contrast ratio between two (r, g, b) colors."""
    l1 = _relative_luminance(rgb1)
    l2 = _relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestViewResultsButtonCssRule(unittest.TestCase):
    """Validates: Requirements 1.1, 1.3."""

    def setUp(self):
        """Load the admin stylesheet content once for all assertions."""
        self.css = _read(STYLE_CSS_PATH)

    def test_global_button_text_rule_unmodified(self):
        """The pre-existing global button text-color rule is retained unmodified."""
        # Arrange: build a whitespace-tolerant pattern for the exact rule
        pattern = re.compile(
            r'button\[class\*="text-"\]\s*\{\s*color:\s*#f4e8d0\s*!important;\s*\}'
        )
        # Act
        match = pattern.search(self.css)
        # Assert
        self.assertIsNotNone(
            match, 'Global rule button[class*="text-"] { color: #f4e8d0 !important; } must remain unmodified'
        )

    def test_view_results_btn_rule_defines_expected_color(self):
        """A dedicated .view-results-btn rule sets color: #1e3a5f !important."""
        # Arrange
        pattern = re.compile(
            r'\.view-results-btn\s*\{\s*color:\s*#1e3a5f\s*!important;\s*\}'
        )
        # Act
        match = pattern.search(self.css)
        # Assert
        self.assertIsNotNone(match, '.view-results-btn { color: #1e3a5f !important; } rule not found')

    def test_view_results_btn_rule_positioned_after_global_rule(self):
        """The .view-results-btn rule appears after the global button text rule."""
        # Arrange
        global_rule_match = re.search(r'button\[class\*="text-"\]', self.css)
        view_results_match = re.search(r'\.view-results-btn\s*\{', self.css)
        # Act / Assert
        self.assertIsNotNone(global_rule_match, 'Global button[class*="text-"] rule not found')
        self.assertIsNotNone(view_results_match, '.view-results-btn rule not found')
        self.assertGreater(
            view_results_match.start(),
            global_rule_match.start(),
            '.view-results-btn rule must be positioned after the global button[class*="text-"] rule'
        )


class TestViewResultsButtonContrastRatio(unittest.TestCase):
    """Validates: Requirements 1.1."""

    def test_contrast_ratio_meets_minimum(self):
        """The #1e3a5f text color against the button's composited background meets 4.5:1."""
        # Arrange: gold background rgba(218,165,32,0.15) composited over white
        background_rgb = _composite_over_white(_hex_to_rgb('#DAA520'), 0.15)
        text_rgb = _hex_to_rgb('#1e3a5f')
        # Act
        ratio = _contrast_ratio(text_rgb, background_rgb)
        # Assert
        self.assertGreaterEqual(
            ratio, 4.5, f'Contrast ratio {ratio:.2f}:1 is below the WCAG AA minimum of 4.5:1'
        )


class TestViewResultsButtonMarkup(unittest.TestCase):
    """Validates: Requirements 1.2, 1.5."""

    def setUp(self):
        """Extract the View Results button markup from manage.html."""
        html = _read(MANAGE_HTML_PATH)
        # Locate the click handler first, then expand outward to the enclosing
        # <button ...> ... </button> markup. A plain regex spanning the whole
        # tag is unreliable here because the x-show attribute value itself
        # contains a literal '>' character (log.result_count > 0).
        anchor = html.find('@click="openResultsModal(log)"')
        self.assertNotEqual(anchor, -1, 'View Results button click handler not found in manage.html')
        tag_start = html.rfind('<button', 0, anchor)
        self.assertNotEqual(tag_start, -1, 'Opening <button tag not found before click handler')
        tag_end = html.find('</button>', anchor)
        self.assertNotEqual(tag_end, -1, 'Closing </button> tag not found after click handler')
        self.button_html = html[tag_start:tag_end + len('</button>')]

    def test_view_results_btn_class_present(self):
        """The button's class attribute includes the view-results-btn class."""
        class_match = re.search(r'class="([^"]*)"', self.button_html)
        self.assertIsNotNone(class_match, 'Button has no class attribute')
        classes = class_match.group(1).split()
        self.assertIn('view-results-btn', classes)

    def test_no_inline_color_declaration(self):
        """The button's inline style no longer sets a color declaration."""
        style_match = re.search(r'style="([^"]*)"', self.button_html)
        self.assertIsNotNone(style_match, 'Button has no style attribute')
        self.assertNotIn('color:', style_match.group(1))

    def test_background_and_border_preserved(self):
        """The button retains its original background and border inline styles."""
        style_match = re.search(r'style="([^"]*)"', self.button_html)
        self.assertIsNotNone(style_match, 'Button has no style attribute')
        style_value = style_match.group(1)
        self.assertIn('background: rgba(218,165,32,0.15)', style_value)
        self.assertIn('border: 1px solid #DAA520', style_value)

    def test_label_text_preserved(self):
        """The button retains its Hebrew label text."""
        self.assertIn('צפה בתוצאות', self.button_html)


class TestResultsModalScrollabilityFix(unittest.TestCase):
    """Tests for the Results Modal scrollability fix.

    Validates: Requirements 2.1, 2.2, 2.3
    """

    def setUp(self):
        """Load the admin stylesheet and manage.html content once for all assertions."""
        self.style_css = _read(STYLE_CSS_PATH)
        self.manage_html = _read(MANAGE_HTML_PATH)

    def test_results_modal_container_base_max_height(self):
        """style.css defines .results-modal-container with max-height: 85vh."""
        # Arrange/Act: search for the base (non-media-query) rule
        pattern = re.compile(
            r'\.results-modal-container\s*\{\s*max-height:\s*85vh;\s*\}'
        )
        # Assert
        self.assertRegex(
            self.style_css,
            pattern,
            'Expected .results-modal-container { max-height: 85vh; } in style.css'
        )

    def test_results_modal_container_media_query_max_height(self):
        """The @media (max-width: 640px) block sets .results-modal-container to max-height: 80vh."""
        # Arrange/Act: search for the media query block containing the override rule
        media_query_pattern = re.compile(
            r'@media\s*\(max-width:\s*640px\)\s*\{'
            r'\s*\.results-modal-container\s*\{'
            r'\s*max-height:\s*80vh;'
            r'\s*\}'
            r'\s*\}'
        )
        # Assert
        self.assertRegex(
            self.style_css,
            media_query_pattern,
            'Expected @media (max-width: 640px) block setting '
            '.results-modal-container max-height to 80vh in style.css'
        )

    def test_manage_html_modal_container_uses_new_class(self):
        """The Results Modal container markup includes results-modal-container and
        no longer includes max-h-[85vh]."""
        # Assert: new class is present
        self.assertIn(
            'results-modal-container',
            self.manage_html,
            'Expected results-modal-container class in frontend/manage.html'
        )
        # Assert: old Tailwind class is gone
        self.assertNotIn(
            'max-h-[85vh]',
            self.manage_html,
            'max-h-[85vh] should have been removed from frontend/manage.html'
        )

    def test_manage_html_scroll_container_unchanged(self):
        """The nested overflow-y-auto flex-1 scroll container element is still
        present and unchanged."""
        # Assert: the scrollable content div is present with its original classes
        self.assertIn(
            'class="px-6 pb-6 overflow-y-auto flex-1"',
            self.manage_html,
            'Expected the nested scroll container '
            '<div class="px-6 pb-6 overflow-y-auto flex-1"> to remain unchanged'
        )


class TestNonRegressionOtherButtonsAndModals(unittest.TestCase):
    """Non-regression checks: other buttons/modals in the Admin_Panel and the
    pirush button/modal in index.html must be untouched by the View Results
    button and Results Modal fixes, and style.css's pre-existing rules
    (including the ones the fixes deliberately avoid modifying) must remain
    present unmodified.

    Validates: Requirements 3.1, 3.2, 3.3
    """

    def setUp(self):
        """Load the admin stylesheet, manage.html, and index.html content once."""
        self.style_css = _read(STYLE_CSS_PATH)
        self.manage_html = _read(MANAGE_HTML_PATH)
        self.index_html = _read(os.path.join(REPO_ROOT, 'frontend', 'index.html'))

    # --- Property 5: other buttons' class/style attributes unchanged ---

    def test_search_logs_pagination_prev_button_unchanged(self):
        """The search log 'הקודם' (previous) pagination button markup is untouched."""
        expected = (
            '<button type="button" @click="logsPage > 1 && (logsPage--, fetchSearchLogs())"\n'
            '                                    :disabled="logsPage <= 1"\n'
            '                                    class="px-4 py-2 rounded-xl font-bold text-sm transition-all duration-200"\n'
            '                                    style="background: rgba(25,25,112,0.1); color: #191970; border: 2px solid rgba(25,25,112,0.3);"\n'
            "                                    :class=\"{ 'opacity-40 cursor-not-allowed': logsPage <= 1 }\">"
        )
        self.assertIn(expected, self.manage_html)

    def test_search_logs_pagination_next_button_unchanged(self):
        """The search log 'הבא' (next) pagination button markup is untouched."""
        expected = (
            '<button type="button" @click="logsPage * logsPageSize < logsTotalCount && (logsPage++, fetchSearchLogs())"\n'
            '                                    :disabled="logsPage * logsPageSize >= logsTotalCount"\n'
            '                                    class="px-4 py-2 rounded-xl font-bold text-sm transition-all duration-200"\n'
            '                                    style="background: rgba(25,25,112,0.1); color: #191970; border: 2px solid rgba(25,25,112,0.3);"\n'
            "                                    :class=\"{ 'opacity-40 cursor-not-allowed': logsPage * logsPageSize >= logsTotalCount }\">"
        )
        self.assertIn(expected, self.manage_html)

    def test_results_modal_retry_button_unchanged(self):
        """The Results Modal's 'נסה שוב' (retry) button markup is untouched."""
        expected = (
            '<button @click="retryResultsModal()" class="main-search-btn px-6 py-2 rounded-xl font-bold">'
        )
        self.assertIn(expected, self.manage_html)

    def test_logout_button_unchanged(self):
        """The admin panel logout button markup is untouched."""
        expected = (
            '<button type="button" @click="logout()"\n'
        )
        self.assertIn(expected, self.manage_html)
        expected_class = (
            'class="bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 '
            'hover:to-red-700 text-white font-bold py-2 px-4 rounded-xl '
            'transition-all duration-200 shadow-lg hover:shadow-xl"'
        )
        self.assertIn(expected_class, self.manage_html)

    def test_pirush_btn_used_unchanged_in_index_html(self):
        """The pirush button in index.html still uses the unmodified .pirush-btn class."""
        self.assertIn('class="pirush-btn"', self.index_html)

    # --- Property 6: other modals' sizing/scroll/class attributes unchanged ---

    def test_edit_tag_confirmation_modal_unchanged(self):
        """The edit-tag confirmation modal container markup is untouched."""
        expected = (
            '<div x-show="showEditConfirm"\n'
            '                                 x-transition:enter="transition ease-out duration-300"\n'
            '                                 x-transition:enter-start="opacity-0"\n'
            '                                 x-transition:enter-end="opacity-100"\n'
            '                                 class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"\n'
            '                                 style="z-index: 10000;" @click.self="showEditConfirm = false">\n'
            '                                <div class="bg-white p-8 rounded-2xl shadow-2xl max-w-md mx-4 border border-gray-100" @click.stop>'
        )
        self.assertIn(expected, self.manage_html)

    def test_delete_user_confirmation_modal_unchanged(self):
        """The delete-user confirmation modal container markup is untouched."""
        expected = (
            '<div x-show="showDeleteUserConfirm" x-cloak\n'
            '                     class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"\n'
            '                     style="z-index: 10000;" @click.self="showDeleteUserConfirm = false">\n'
            '                    <div class="bg-white p-8 rounded-2xl shadow-2xl max-w-md mx-4 border border-gray-100" @click.stop>'
        )
        self.assertIn(expected, self.manage_html)

    def test_pirush_modal_content_used_unchanged_in_index_html(self):
        """The pirush modal in index.html still uses the unmodified .pirush-modal-content class
        (no max-h-[...] or results-modal-container class was introduced there)."""
        self.assertIn('class="relative pirush-modal-content"', self.index_html)
        self.assertNotIn('results-modal-container', self.index_html)

    # --- Property 5 & 6 combined: style.css changes are purely additive ---

    def test_pirush_btn_css_rules_unmodified(self):
        """The pre-existing .pirush-btn rule blocks remain present unmodified."""
        expected_blocks = [
            '.pirush-btn {\n'
            '    display: inline-flex;\n'
            '    align-items: center;\n'
            '    justify-content: center;\n'
            '    background: linear-gradient(135deg, #DAA520 0%, #B8860B 100%) !important;\n'
            '    color: #2D2D2D !important;\n'
            '    border: none !important;\n'
            '    border-radius: 16px !important;\n'
            '    padding: 10px 24px !important;\n'
            '    font-weight: 700 !important;\n'
            '    font-size: 1rem !important;\n'
            '    cursor: pointer !important;\n'
            '    text-decoration: none !important;\n'
            '    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;\n'
            '    box-shadow: 0 4px 12px rgba(218, 165, 32, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;\n'
            '    text-shadow: none !important;\n'
            '}',
            '.pirush-btn:hover {\n'
            '    background: linear-gradient(135deg, #FFD700 0%, #DAA520 100%) !important;\n'
            '    color: #2D2D2D !important;\n'
            '    transform: translateY(-2px) !important;\n'
            '    box-shadow: 0 8px 24px rgba(218, 165, 32, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.3) !important;\n'
            '}',
            '.pirush-btn:focus-visible {\n'
            '    outline: 2px solid #DAA520 !important;\n'
            '    outline-offset: 2px !important;\n'
            '}',
            '.pirush-btn svg {\n'
            '    color: #2D2D2D !important;\n'
            '    stroke: #2D2D2D !important;\n'
            '}',
        ]
        for block in expected_blocks:
            self.assertIn(block, self.style_css)

    def test_pirush_modal_content_css_rules_unmodified(self):
        """The pre-existing .pirush-modal-content rule blocks remain present unmodified."""
        expected_blocks = [
            '.pirush-modal-content {\n'
            '    position: relative;\n'
            '    display: flex;\n'
            '    flex-direction: column;\n'
            '    width: 80%;\n'
            '    height: 85vh;\n'
            '    background: rgba(15, 25, 40, 0.92) !important;\n'
            '    backdrop-filter: blur(20px) saturate(180%) !important;\n'
            '    border: 1px solid rgba(218, 165, 32, 0.3) !important;\n'
            '    border-radius: 20px !important;\n'
            '    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(218, 165, 32, 0.15) !important;\n'
            '    overflow: hidden;\n'
            '    outline: none;\n'
            '}',
            '@media (max-width: 768px) {\n'
            '    .pirush-modal-content {\n'
            '        width: 95% !important;\n'
            '        height: 90vh !important;\n'
            '        border-radius: 16px !important;\n'
            '    }\n'
            '}',
        ]
        for block in expected_blocks:
            self.assertIn(block, self.style_css)

    def test_style_css_additions_are_the_only_new_content(self):
        """The two new rule blocks are located together, immediately after the
        global button[class*="text-"] rule, and the content preceding and
        following that insertion point (the rest of the stylesheet) contains
        all other pre-existing rules verified above, i.e. the diff is purely
        additive at a single insertion point."""
        # Arrange: locate the global rule and the new blocks
        global_rule_pattern = re.compile(
            r'button\[class\*="text-"\]\s*\{\s*color:\s*#f4e8d0\s*!important;\s*\}'
        )
        global_match = global_rule_pattern.search(self.style_css)
        self.assertIsNotNone(global_match, 'Global button[class*="text-"] rule not found')

        # Act: the two new blocks should appear directly after the global rule,
        # before the next pre-existing section comment that followed it originally
        # (SPECIFIC STYLING FOR ONLY THE 3 SEARCH OPTION BUTTONS).
        tail = self.style_css[global_match.end():]
        next_section_match = re.search(
            r'/\* ={5}\s*S\s*PECIFIC STYLING FOR ONLY THE 3 SEARCH OPTION BUTTONS\s*={5} \*/',
            tail,
        )
        self.assertIsNotNone(
            next_section_match,
            'Expected the pre-existing "SPECIFIC STYLING FOR ONLY THE 3 SEARCH OPTION '
            'BUTTONS" section comment to still follow the inserted rules'
        )
        between = tail[:next_section_match.start()]

        # Assert: only the two new rule blocks (and whitespace/comments) sit between
        # the global rule and the next pre-existing section.
        self.assertIn('.view-results-btn', between)
        self.assertIn('.results-modal-container', between)
        self.assertIn('@media (max-width: 640px)', between)


if __name__ == '__main__':
    unittest.main()
