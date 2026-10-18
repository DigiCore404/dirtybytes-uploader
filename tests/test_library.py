import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.library import match_category, validate_rules
from utils.app_version import SLUG
from utils.web_settings import defaults


class LibraryRulesTests(unittest.TestCase):
    def setUp(self):
        filename = 'digitalcore-categories.json' if SLUG == 'digitalcore-uploader' else 'dirtybytes-categories.json'
        self.categories = json.loads((ROOT / 'files' / filename).read_text(encoding='utf-8'))

    def test_empty_regex_is_a_valid_catch_all_in_cli_and_preview(self):
        category = self.categories[0]
        rules = {'G': {'patterns': {'initial': ['Sample']}, 'categories': [{'cat_id': str(category['id']), 'patterns': ['']} ]}}
        self.assertEqual(match_category('Sample.Release', rules, self.categories)['id'], category['id'])
        with patch('utils.config_loader.ConfigLoader') as loader:
            loader.return_value.get_config.return_value = defaults()
            module = importlib.import_module('utils.category_utils')
        self.assertTrue(module._search_any([''], 'Sample.Release'))

    def test_first_match_and_exclusions_follow_filter_order(self):
        first, second = self.categories[:2]
        rules = {'G': {'patterns': {'initial': ['Sample']}, 'categories': [
            {'cat_id': str(first['id']), 'patterns': ['Sample']},
            {'cat_id': str(second['id']), 'patterns': ['Sample']}]}}
        self.assertEqual(match_category('Sample', rules, self.categories)['id'], first['id'])
        rules['G']['categories'][0]['exclude_patterns'] = ['']
        self.assertEqual(match_category('Sample', rules, self.categories)['id'], second['id'])

    def test_shipped_filters_recognize_uhd_movie_names(self):
        rules = validate_rules((ROOT / 'files/filters.json').read_text(encoding='utf-8'), self.categories)
        result = match_category('Example.Movie.2026.2160p.WEB-DL.H265-GROUP.mkv', rules, self.categories)
        self.assertEqual(result['name'], 'Movies/2160p')

    def test_invalid_default_type_is_rejected(self):
        rule = {'G': {'patterns': {'initial': ['x']}, 'categories': [{'cat_id': str(self.categories[0]['id']), 'default': 'false'}]}}
        with self.assertRaises(ValueError):
            validate_rules(json.dumps(rule), self.categories)
