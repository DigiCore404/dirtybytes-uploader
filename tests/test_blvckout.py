import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import blvckout
from utils.web_settings import defaults, schema
from utils.connection_tests import check


class BlvckoutTests(unittest.TestCase):
    def test_schema_maps_real_fields_and_strips_html(self):
        row={'id':'abc-123','title':'Example','release_date':'2026-10-01','year':2026,'production_year':2025,
             'runtime_minutes':95,'studio':'Example Studio','performers':['A','B'],'genres':['Drama','Comedy'],
             'notes':'<p>First paragraph</p><p>Second paragraph</p>',
             'front_cover':'https://cdn.example/front.jpg','back_cover':'https://cdn.example/back.png'}
        result=blvckout.normalize(row)
        self.assertEqual(result['metadata'],{'studio':'Example Studio','performers':'A, B','content_tags':'Drama, Comedy','release_year':'2025','runtime_minutes':'95'})
        self.assertEqual(result['description'],'First paragraph\n\nSecond paragraph')
        self.assertEqual(result['images'],[row['front_cover'],row['back_cover']])

    def test_fixed_origin_bearer_key_and_no_redirects(self):
        session=Mock();session.get.return_value.status_code=200;session.get.return_value.json.return_value={'items':[]}
        with patch.object(blvckout.requests,'Session') as factory:
            factory.return_value.__enter__.return_value=session
            self.assertEqual(blvckout.search('private-test-key','Example'),[])
        args,kwargs=session.get.call_args
        self.assertEqual(args[0],'https://blvckout.foo/api/v1/releases')
        self.assertEqual(kwargs['headers']['Authorization'],'Bearer private-test-key')
        self.assertEqual(kwargs['params'],{'q':'Example','limit':12})
        self.assertFalse(kwargs['allow_redirects']);self.assertFalse(session.trust_env)

    def test_detail_is_validated_and_keys_never_appear_in_errors(self):
        with patch.object(blvckout,'request') as request:
            with self.assertRaises(ValueError):blvckout.detail('secret','../../other')
            request.assert_not_called()
        response=Mock(status_code=401)
        with patch.object(blvckout.requests,'Session') as factory:
            factory.return_value.__enter__.return_value.get.return_value=response
            with self.assertRaisesRegex(ValueError,'rejected this key'):blvckout.search('private-test-key','Example')

    def test_key_is_not_exposed_by_generic_settings_and_connection_test_uses_me(self):
        config=defaults();config.set('BLVCKOUT','API_KEY','private-test-key')
        self.assertNotIn('private-test-key',str(schema(config)))
        with patch.object(blvckout,'request',return_value={'id':'example-user'}) as request:
            self.assertTrue(check(config,{'target':'blvckout'})['ok'])
            request.assert_called_once_with('private-test-key','/me')

    def test_tag_limit_is_deduplicated_before_tracker_publication(self):
        from utils.metadata_text import bounded_names
        value='Drama, drama, '+', '.join('Tag '+str(i) for i in range(20))
        result=bounded_names(value).split(', ')
        self.assertEqual(len(result),12)
        self.assertEqual(result[0],'Drama')
        self.assertEqual(len(blvckout.normalize({'genres':['Tag '+str(i) for i in range(20)]})['metadata']['content_tags'].split(', ')),12)
