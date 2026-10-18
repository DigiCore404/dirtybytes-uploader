import base64
import configparser
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import image_host
GIF=base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
class ImgBBTests(unittest.TestCase):
    def setUp(self):
        self.config=configparser.ConfigParser(interpolation=None);self.config.read(ROOT/'defaults.ini',encoding='utf-8')
        self.config.set('Website','API_KEY','site-key-not-for-imgbb')
        self.config.set('ImageHost','PROVIDER','imgbb');self.config.set('ImageHost','API_KEY','imgbb-private-key')
    def response(self,value,code=200):
        result=requests.Response();result.status_code=code;result._content=json.dumps(value).encode();return result
    def test_official_imgbb_multipart_contract_and_direct_image_url(self):
        session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False)
        session.post.return_value=self.response({'success':True,'data':{'url':'https://i.ibb.co/example/cover.gif','url_viewer':'https://ibb.co/example','delete_url':'https://ibb.co/private-delete'}})
        with patch.object(image_host.requests,'Session',return_value=session):
            result=image_host.upload(self.config,'cover.gif',GIF)
        args,kw=session.post.call_args
        self.assertEqual(args[0],'https://api.imgbb.com/1/upload')
        self.assertNotIn('?',args[0]);self.assertEqual(kw['headers'],{})
        self.assertEqual(kw['data'],{'key':'imgbb-private-key','name':'cover'})
        self.assertEqual(kw['files']['image'][1],GIF)
        self.assertFalse(kw['allow_redirects']);self.assertFalse(session.trust_env)
        self.assertEqual(result,{'url':'https://i.ibb.co/example/cover.gif','provider':'imgbb'})
    def test_missing_key_and_failed_or_unsafe_responses(self):
        self.config.set('ImageHost','API_KEY','')
        with self.assertRaisesRegex(ValueError,'ImgBB API key'):image_host.post(self.config,'cover.gif',GIF)
        for row in ({'success':False,'data':{'url':'https://i.ibb.co/example/a.gif'}},{'data':{'url':'javascript:alert(1)'}},{'data':{'url':'https://user:private@example.com/a.gif'}}):
            self.assertEqual(image_host.image_url(self.response(row)),'')
        with patch.object(image_host,'post',return_value=self.response({'error':'imgbb-private-key'},400)):
            with self.assertRaises(ValueError) as error:image_host.upload(self.config,'cover.gif',GIF)
        self.assertNotIn('imgbb-private-key',str(error.exception))
