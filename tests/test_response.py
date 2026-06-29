"""Unit tests for API Gateway response helpers and Mishna serialization."""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from layers.shared.python.response import (
    success_response,
    error_response,
    serialize_mishna,
    serialize_favorite,
    serialize_search_log,
)


class TestSuccessResponse(unittest.TestCase):

    def test_default_status_200(self):
        """success_response returns 200 by default."""
        result = success_response({'ok': True})
        self.assertEqual(result['statusCode'], 200)

    def test_custom_status(self):
        """success_response respects a custom status code."""
        result = success_response({'created': True}, status=201)
        self.assertEqual(result['statusCode'], 201)

    def test_content_type_header(self):
        """Response includes Content-Type: application/json."""
        result = success_response([])
        self.assertEqual(result['headers']['Content-Type'], 'application/json')

    def test_hebrew_preserved(self):
        """Hebrew characters are preserved (ensure_ascii=False)."""
        result = success_response({'msg': 'שלום'})
        self.assertIn('שלום', result['body'])

    def test_body_is_json_string(self):
        """Body is a valid JSON string."""
        payload = {'a': 1, 'b': [2, 3]}
        result = success_response(payload)
        self.assertEqual(json.loads(result['body']), payload)


class TestErrorResponse(unittest.TestCase):

    def test_error_structure(self):
        """Error response contains error and code keys."""
        result = error_response('לא נמצא', 'NOT_FOUND', 404)
        body = json.loads(result['body'])
        self.assertEqual(body['error'], 'לא נמצא')
        self.assertEqual(body['code'], 'NOT_FOUND')

    def test_status_code(self):
        """Error response uses the provided status code."""
        result = error_response('שגיאה', 'INTERNAL_ERROR', 500)
        self.assertEqual(result['statusCode'], 500)

    def test_content_type_header(self):
        """Error response includes Content-Type: application/json."""
        result = error_response('msg', 'VALIDATION_ERROR', 400)
        self.assertEqual(result['headers']['Content-Type'], 'application/json')

    def test_hebrew_in_error(self):
        """Hebrew error message is preserved without escaping."""
        result = error_response('חרגת ממגבלת הבקשות', 'RATE_LIMITED', 429)
        self.assertIn('חרגת ממגבלת הבקשות', result['body'])


class TestSerializeMishna(unittest.TestCase):

    def _make_tag(self, id, name, category_id=None, category=None):
        """Create a mock Tag object."""
        tag = MagicMock()
        tag.id = id
        tag.name = name
        tag.category_id = category_id
        tag.category = category
        return tag

    def _make_category(self, name, color):
        """Create a mock Category object."""
        cat = MagicMock()
        cat.name = name
        cat.color = color
        return cat

    def _make_mishna(self, tags=None):
        """Create a mock Mishna object."""
        m = MagicMock()
        m.id = 'א_א'
        m.chapter = 'א'
        m.mishna = 'א'
        m.number = 1
        m.text_pretty = 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי'
        m.text_raw = 'משה קבל תורה מסיני'
        m.interpretation = 'פירוש'
        m.pirush_url = 'https://example.com/pirush'
        m.tags = tags or []
        return m

    def test_all_top_level_keys(self):
        """Validates: Requirements 2.8 — all required keys present."""
        mishna = self._make_mishna()
        result = serialize_mishna(mishna)
        expected_keys = {
            'id', 'chapter', 'mishna', 'number',
            'text_pretty', 'text_raw', 'interpretation',
            'pirush_url', 'tags'
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_tag_with_category(self):
        """Tag serialization includes category name and color."""
        cat = self._make_category('מוסר', '#FF0000')
        tag = self._make_tag(1, 'ענווה', category_id=1, category=cat)
        mishna = self._make_mishna(tags=[tag])

        result = serialize_mishna(mishna)
        tag_dict = result['tags'][0]
        self.assertEqual(tag_dict['category_name'], 'מוסר')
        self.assertEqual(tag_dict['category_color'], '#FF0000')

    def test_tag_without_category_defaults(self):
        """Tag without category falls back to כללי and #F5F5F5."""
        tag = self._make_tag(2, 'חכמה', category_id=None, category=None)
        mishna = self._make_mishna(tags=[tag])

        result = serialize_mishna(mishna)
        tag_dict = result['tags'][0]
        self.assertEqual(tag_dict['category_name'], 'כללי')
        self.assertEqual(tag_dict['category_color'], '#F5F5F5')

    def test_tag_keys(self):
        """Each tag dict contains all required keys."""
        cat = self._make_category('כללי', '#F5F5F5')
        tag = self._make_tag(1, 'תג', category_id=1, category=cat)
        mishna = self._make_mishna(tags=[tag])

        result = serialize_mishna(mishna)
        tag_dict = result['tags'][0]
        expected_tag_keys = {'id', 'name', 'category_id', 'category_name', 'category_color'}
        self.assertEqual(set(tag_dict.keys()), expected_tag_keys)

    def test_empty_tags(self):
        """Mishna with no tags returns empty tags list."""
        mishna = self._make_mishna(tags=[])
        result = serialize_mishna(mishna)
        self.assertEqual(result['tags'], [])

    def test_none_interpretation_and_pirush(self):
        """Null interpretation and pirush_url are serialized as None."""
        mishna = self._make_mishna()
        mishna.interpretation = None
        mishna.pirush_url = None
        result = serialize_mishna(mishna)
        self.assertIsNone(result['interpretation'])
        self.assertIsNone(result['pirush_url'])

    def test_field_values_match(self):
        """Serialized values match the source Mishna object."""
        mishna = self._make_mishna()
        result = serialize_mishna(mishna)
        self.assertEqual(result['id'], 'א_א')
        self.assertEqual(result['chapter'], 'א')
        self.assertEqual(result['number'], 1)
        self.assertEqual(result['text_pretty'], 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי')


class TestSerializeFavorite(unittest.TestCase):

    def _make_tag(self, name):
        tag = MagicMock()
        tag.name = name
        return tag

    def _make_mishna(self, tags=None):
        m = MagicMock()
        m.chapter = 'א'
        m.mishna = 'ב'
        m.text_pretty = 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי'
        m.tags = tags or []
        return m

    def _make_favorite(self, tags=None):
        fav = MagicMock()
        fav.id = 42
        fav.mishna_id = 'א_ב'
        fav.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        fav.mishna = self._make_mishna(tags=tags)
        return fav

    def test_top_level_keys(self):
        """Validates: Requirements 8.2 — all required top-level keys present."""
        fav = self._make_favorite()
        result = serialize_favorite(fav)
        self.assertEqual(set(result.keys()), {'id', 'mishna_id', 'created_at', 'mishna'})

    def test_mishna_nested_keys(self):
        """Validates: Requirements 8.2 — nested mishna dict has required keys."""
        fav = self._make_favorite()
        result = serialize_favorite(fav)
        self.assertEqual(set(result['mishna'].keys()), {'chapter', 'mishna', 'text_pretty', 'tags'})

    def test_field_values(self):
        """Serialized values match the source UserFavorite object."""
        fav = self._make_favorite()
        result = serialize_favorite(fav)
        self.assertEqual(result['id'], 42)
        self.assertEqual(result['mishna_id'], 'א_ב')
        self.assertEqual(result['mishna']['chapter'], 'א')
        self.assertEqual(result['mishna']['mishna'], 'ב')
        self.assertEqual(result['mishna']['text_pretty'], 'מֹשֶׁה קִבֵּל תּוֹרָה מִסִּינַי')

    def test_created_at_iso_format(self):
        """created_at is serialized as an ISO format string."""
        fav = self._make_favorite()
        result = serialize_favorite(fav)
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result['created_at'])
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 6)
        self.assertEqual(parsed.day, 1)

    def test_tags_are_name_strings(self):
        """Tags in nested mishna dict are a list of tag name strings."""
        tags = [self._make_tag('ענווה'), self._make_tag('חכמה')]
        fav = self._make_favorite(tags=tags)
        result = serialize_favorite(fav)
        self.assertEqual(result['mishna']['tags'], ['ענווה', 'חכמה'])

    def test_empty_tags(self):
        """Favorite with no tags returns empty tags list."""
        fav = self._make_favorite(tags=[])
        result = serialize_favorite(fav)
        self.assertEqual(result['mishna']['tags'], [])


class TestSerializeSearchLog(unittest.TestCase):

    def _make_log(self, user_sub=None, result_ids=None):
        log = MagicMock()
        log.id = 7
        log.query_text = 'מה ההבדל בין חכמה לבינה'
        log.result_count = 3
        log.result_ids = result_ids
        log.user_sub = user_sub
        log.created_at = datetime(2024, 7, 15, 9, 30, 0, tzinfo=timezone.utc)
        return log

    def test_all_keys_present(self):
        """Validates: Requirements 7.4 — all required keys present."""
        log = self._make_log()
        result = serialize_search_log(log)
        self.assertEqual(
            set(result.keys()),
            {'id', 'query_text', 'result_count', 'result_ids', 'user_sub', 'created_at'}
        )

    def test_field_values(self):
        """Serialized values match the source AiSearchLog object."""
        log = self._make_log(user_sub='abc-123', result_ids='א_א,א_ב,א_ג')
        result = serialize_search_log(log)
        self.assertEqual(result['id'], 7)
        self.assertEqual(result['query_text'], 'מה ההבדל בין חכמה לבינה')
        self.assertEqual(result['result_count'], 3)
        self.assertEqual(result['result_ids'], 'א_א,א_ב,א_ג')
        self.assertEqual(result['user_sub'], 'abc-123')

    def test_created_at_iso_format(self):
        """created_at is serialized as an ISO format string."""
        log = self._make_log()
        result = serialize_search_log(log)
        parsed = datetime.fromisoformat(result['created_at'])
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 7)
        self.assertEqual(parsed.day, 15)

    def test_nullable_fields_preserved(self):
        """Nullable user_sub and result_ids are serialized as None."""
        log = self._make_log(user_sub=None, result_ids=None)
        result = serialize_search_log(log)
        self.assertIsNone(result['user_sub'])
        self.assertIsNone(result['result_ids'])


if __name__ == '__main__':
    unittest.main()
