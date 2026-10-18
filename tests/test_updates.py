from pathlib import Path
import os
import sys
import unittest
from unittest.mock import Mock, patch
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import update_check as updates
from utils.app_version import VERSION, REPOSITORY

class ReleaseTests(unittest.TestCase):
    def response(self,row,code=200):
        response=Mock(status_code=code);response.json.return_value=row;return response
    def test_release_links_are_fixed_to_our_repository_and_versions_are_numeric(self):
        row={'tag_name':'v99.0.0','body':'New features','html_url':'https://untrusted.invalid','assets':[{'browser_download_url':'https://untrusted.invalid'}]}
        with patch.object(updates.requests,'get',return_value=self.response(row)) as request:
            result=updates.latest_release()
        self.assertEqual(result['latest_version'],'99.0.0')
        self.assertEqual(result['release_url'],'https://github.com/'+REPOSITORY+'/releases/tag/v99.0.0')
        args,kw=request.call_args
        self.assertEqual(args,('https://api.github.com/repos/'+REPOSITORY+'/releases/latest',))
        self.assertEqual(kw,{'timeout':5,'allow_redirects':False})
        self.assertGreater(updates.version_parts('v3.10.0'),updates.version_parts('3.9.9'))
        for invalid in ['v3.0.0; touch /tmp/bad','3.0.0-beta','https://evil.invalid','v1.0']:
            with self.assertRaises(ValueError):updates.instructions(invalid)
    def test_disabled_does_not_connect_and_background_checks_are_cached(self):
        checker=updates.ReleaseChecker()
        with patch.object(updates.threading,'Thread') as worker:
            self.assertEqual(checker.status(False)['status'],'disabled');worker.assert_not_called()
            self.assertEqual(checker.status()['status'],'checking');worker.assert_called_once()
            checker.status(force=True);worker.assert_called_once()
        with patch.object(updates,'latest_release',return_value={'latest_version':'99.0.0','release_url':'https://github.com/'+REPOSITORY+'/releases/tag/v99.0.0','notes':'Features'}):checker._check()
        with patch.object(updates.threading,'Thread') as worker:
            result=checker.status();checker.status(force=True);worker.assert_not_called()
        self.assertTrue(result['available']);self.assertEqual(result['status'],'available')
        self.assertEqual(result['current_version'],VERSION)
        self.assertIn('docker compose pull',result['instructions']['docker_commands'])
        self.assertIn('--exclude=config.ini',result['instructions']['package_commands'])
        self.assertIn('sha256sum --check',result['instructions']['package_commands'])
    def test_same_version_no_release_and_network_failures_are_explicit(self):
        for release,status in [(None,'no_release'),({'latest_version':VERSION,'notes':'','release_url':'https://github.com/'+REPOSITORY+'/releases'},'current')]:
            checker=updates.ReleaseChecker()
            with patch.object(updates,'latest_release',return_value=release):checker._check()
            self.assertEqual(checker.status()['status'],status);self.assertFalse(checker.status()['available'])
        checker=updates.ReleaseChecker()
        with patch.object(updates.requests,'get',side_effect=requests.Timeout('private network details')):checker._check()
        self.assertEqual(checker.status()['status'],'unavailable')
        self.assertNotIn('private network details',str(checker.status()))
    def test_cli_notification_still_works(self):
        with patch.object(updates.requests,'get',return_value=self.response({'tag_name':'v99.0.0'})),patch('builtins.print') as emit:
            updates.check(VERSION)
        emit.assert_called_once()

import test_web as web_fixtures
class UpdateApiTests(unittest.TestCase):
    setUp=web_fixtures.WebTests.setUp
    tearDown=web_fixtures.WebTests.tearDown
    login=web_fixtures.WebTests.login
    post=web_fixtures.WebTests.post
    def test_update_endpoints_require_login_and_manual_checks_require_csrf(self):
        self.assertEqual(self.client.get(self.base+'/api/updates').status_code,401)
        self.assertEqual(self.post('/api/updates/check',{}).status_code,401)
        self.login()
        with patch.object(self.server.workspace.updates,'status',return_value={'status':'current','current_version':VERSION}) as status:
            self.assertEqual(self.client.get(self.base+'/api/updates').status_code,200)
            saved=self.csrf;self.csrf='wrong'
            self.assertEqual(self.post('/api/updates/check',{}).status_code,403)
            self.csrf=saved
            self.assertEqual(self.post('/api/updates/check',{}).status_code,200)
            self.assertTrue(status.call_args.kwargs['force'])
        for asset in ['/updates.js','/updates.css']:
            self.assertEqual(self.client.get(self.base+asset).status_code,200)
    def test_imgbb_selection_and_private_key_are_preserved(self):
        import uploader
        self.login()
        response=self.post('/api/settings',{'image_host':'imgbb','image_host_key':'imgbb-private-test-key'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('imgbb-private-test-key',response.text)
        self.assertEqual(uploader.load_config().get('ImageHost','PROVIDER'),'imgbb')
        self.assertEqual(uploader.load_config().get('ImageHost','UPLOADIMGURL'),'https://api.imgbb.com/1/upload')
        self.assertEqual(uploader.load_config().get('ImageHost','API_KEY'),'imgbb-private-test-key')
        self.assertEqual(self.post('/api/settings',{'image_host_key':''}).status_code,200)
        self.assertEqual(uploader.load_config().get('ImageHost','API_KEY'),'imgbb-private-test-key')
        self.assertEqual(self.client.get(self.base+'/api/state').json()['version'],VERSION)
