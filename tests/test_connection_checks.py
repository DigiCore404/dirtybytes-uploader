import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.connection_tests import check
from utils.web_settings import defaults
from utils.app_version import SLUG


class ConnectionChecks(unittest.TestCase):
    def setUp(self):
        self.config = defaults()
        self.config.set('Website', 'API_KEY', 'saved-private-key')
        self.config.set('ImageHost', 'API_KEY', 'saved-image-key')

    def response(self, status=200, payload=None):
        session = Mock()
        session.get.return_value.status_code = status
        session.get.return_value.json.return_value = [] if payload is None else payload
        context = patch('utils.connection_tests.requests.Session')
        factory = context.start()
        self.addCleanup(context.stop)
        factory.return_value.__enter__.return_value = session
        return session

    def test_site_checks_entered_key_without_saving_or_redirects(self):
        before = copy.deepcopy(dict(self.config['Website']))
        session = self.response()
        result = check(self.config, {'target': 'site', 'api_key': 'new-private-key'})
        self.assertTrue(result['ok'])
        self.assertEqual(session.get.call_args.kwargs['headers']['X-API-KEY'], 'new-private-key')
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertFalse(session.trust_env)
        self.assertEqual(dict(self.config['Website']), before)
        self.assertNotIn('private-key', str(result))

    def test_blank_field_uses_saved_key(self):
        session = self.response()
        self.assertTrue(check(self.config, {'target': 'site', 'api_key': ''})['ok'])
        self.assertEqual(session.get.call_args.kwargs['headers']['X-API-KEY'], 'saved-private-key')

    def test_authentication_failure_is_not_success(self):
        self.response(401)
        result = check(self.config, {'target': 'site'})
        self.assertFalse(result['ok'])
        self.assertIn('rejected', result['message'])

    def test_unsuccessful_json_is_not_success(self):
        self.response(payload={'error': 'private-upstream-body'})
        result = check(self.config, {'target': 'site'})
        self.assertFalse(result['ok'])
        self.assertNotIn('private-upstream-body', str(result))

    def test_network_error_does_not_disclose_request_or_key(self):
        session = self.response()
        session.get.side_effect = requests.ConnectionError('url?key=saved-private-key')
        result = check(self.config, {'target': 'site'})
        self.assertFalse(result['ok'])
        self.assertNotIn('saved-private-key', str(result))

    def test_image_test_uses_selected_host_and_unsaved_key(self):
        with patch('utils.connection_tests.image_host.upload', return_value={'url': 'https://example.invalid/test.png'}) as upload:
            result = check(self.config, {'target': 'image_host', 'image_host': 'imgbb', 'image_host_key': 'unsaved-image-key'})
        self.assertTrue(result['ok'])
        tested = upload.call_args.args[0]
        self.assertEqual(tested.get('ImageHost', 'PROVIDER'), 'imgbb')
        self.assertEqual(tested.get('ImageHost', 'API_KEY'), 'unsaved-image-key')
        self.assertEqual(self.config.get('ImageHost', 'API_KEY'), 'saved-image-key')
        self.assertNotIn('unsaved-image-key', str(result))

    def test_custom_host_and_unrelated_test_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            check(self.config, {'target': 'image_host', 'image_host': 'custom'})
        with self.assertRaises(ValueError):
            check(self.config, {'target': 'image_host', 'config_fields': {'Website': {'siteurl': 'https://example.invalid'}}})

    def test_metadata_checks_authenticate_without_saving(self):
        if SLUG == 'digitalcore-uploader':
            with patch('utils.tmdb.request', return_value={'images': {}}) as request:
                self.assertTrue(check(self.config, {'target': 'tmdb', 'tmdb_token': 'temporary-token'})['ok'])
                request.assert_called_once_with('temporary-token', '/configuration')
            with patch('utils.igdb.request', return_value=[]) as request:
                self.assertTrue(check(self.config, {'target': 'igdb', 'igdb_client_id': 'client', 'igdb_client_secret': 'secret'})['ok'])
                request.assert_called_once_with('client', 'secret', 'fields id; limit 1;')
            with patch('utils.tvmaze.request', return_value={'id': 1}):
                self.assertTrue(check(self.config, {'target': 'tvmaze'})['ok'])
        else:
            with patch('utils.tpdb.request', return_value=[]) as request:
                self.assertTrue(check(self.config, {'target': 'tpdb', 'tpdb_token': 'temporary-token'})['ok'])
                request.assert_called_once_with('temporary-token', '/scenes', {'limit': 1})


if __name__ == '__main__':
    unittest.main()
