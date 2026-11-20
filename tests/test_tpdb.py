import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import tpdb


class TpdbImageTests(unittest.TestCase):
    def test_direct_cdn_background_precedes_transformed_poster(self):
        row = {'poster': 'https://thumb.theporndb.net/signature/800x1200/smart/filters:sharpen()/scene%2Fposter',
               'image': 'https://studio.example/original.jpg',
               'background': {'full': 'https://cdn.theporndb.net/scene/full.jpg',
                              'large': 'https://cdn.theporndb.net/scene/large.jpg'}}
        self.assertEqual(tpdb.normalize(row, 'scenes')['images'], [row['background']['large']])

    def test_fallbacks_skip_empty_and_invalid_values(self):
        for background in (None, {}, {'large': '', 'full': 'javascript:bad'}, {'large': []}):
            with self.subTest(background=background):
                row = {'background': background, 'image': 'https://cdn.example/image.png', 'poster': 'https://thumb.example/poster'}
                self.assertEqual(tpdb.normalize(row, 'scenes')['images'], [row['image']])
        self.assertEqual(tpdb.normalize({'background': {'full': 'https://cdn.example/full.webp'}}, 'movies')['images'], ['https://cdn.example/full.webp'])

    def test_extensionless_and_signed_urls_are_not_rewritten(self):
        for url in ('https://cdn.example/image/123', 'https://cdn.example/image.jpg?signature=abc%2Fdef&width=800'):
            self.assertEqual(tpdb.normalize({'image': url}, 'scenes')['images'], [url])

    def test_poster_only_response_remains_supported(self):
        self.assertEqual(tpdb.normalize({'poster': 'https://cdn.example/poster.jpg'}, 'movies')['images'], ['https://cdn.example/poster.jpg'])

    def test_unsafe_candidates_are_rejected(self):
        for url in ('https://user:password@cdn.example/a.jpg', 'https://cdn.example/a.jpg\n', 'https://cdn.example/a[/img].jpg', 'http://cdn.example/a.jpg', 'https://[broken'):
            with self.subTest(url=url):
                self.assertEqual(tpdb.normalize({'image': url}, 'scenes')['images'], [])

    def test_search_and_detail_share_image_selection(self):
        row = {'id': 'fixture', 'poster': 'https://thumb.example/transformed', 'background': {'large': 'https://cdn.example/direct.jpg'}}
        with patch.object(tpdb, 'request', side_effect=[[row], row]):
            self.assertEqual(tpdb.search('fixture-token', 'Example')[0]['images'], ['https://cdn.example/direct.jpg'])
            self.assertEqual(tpdb.detail('fixture-token', 'fixture', 'scenes')['images'], ['https://cdn.example/direct.jpg'])


class TpdbMetadataTests(unittest.TestCase):
    def test_canonical_parent_name_wins_over_scene_alias(self):
        row = {'performers': [
            {'name':'Sapphire 950','parent':{'name':'Sapphire May'}},
            {'name':'Jay','parent':{'name':'Jay Romero'}},
            {'name':'Another alias','parent':{'name':'Sapphire May'}},
            {'name':'Fallback','parent':None},
            {'name':'Fallback','parent':{'name':'  '}},
            None]}
        self.assertEqual(tpdb.normalize(row,'scenes')['metadata']['performers'],'Sapphire May, Jay Romero, Fallback')

    def test_duration_is_converted_to_bounded_whole_minutes(self):
        for raw,expected in [(1800,'30'),('1831','31'),('01:30:00','90'),('30:29','30'),(1,'1'),(None,''),(0,''),(-1,''),(float('nan'),''),(float('inf'),''),(True,''),('invalid',''),(120001,'')]:
            with self.subTest(raw=raw):self.assertEqual(tpdb.normalize({'duration':raw},'scenes')['metadata']['runtime_minutes'],expected)
        self.assertEqual(tpdb.runtime_minutes({'runtime_minutes':'45','duration':900}),'45')

    def test_search_and_detail_both_include_canonical_names_and_runtime(self):
        row={'id':'sample','duration':3600,'performers':[{'name':'Alias','parent':{'name':'Full Name'}}]}
        with patch.object(tpdb,'request',side_effect=[[row],row]):
            for result in [tpdb.search('test-token','Example')[0],tpdb.detail('test-token','sample','scenes')]:
                self.assertEqual(result['metadata']['performers'],'Full Name')
                self.assertEqual(result['metadata']['runtime_minutes'],'60')
