import base64
import configparser
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import image_host,public_download

GIF=base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

class ImageHostTests(unittest.TestCase):
 def setUp(self):
  self.config=configparser.ConfigParser(interpolation=None);self.config.read(ROOT/'defaults.ini',encoding='utf-8')
  self.config.set('Website','API_KEY','private-site-key');self.config.set('ImageHost','API_KEY','private-image-key')
 def response(self,value,code=200):
  r=requests.Response();r.status_code=code;r._content=json.dumps(value).encode();return r
 def test_imghost_upload_contract_does_not_send_key_in_url(self):
  self.config.set('ImageHost','PROVIDER','imghost');self.config.set('ImageHost','UPLOADIMGURL','https://wrong.invalid')
  session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False)
  session.post.return_value=self.response({'image':{'url':'https://imghost.dev/images/test.gif'}})
  with patch.object(image_host.requests,'Session',return_value=session):
   result=image_host.upload(self.config,'cover.gif',GIF)
  args,kw=session.post.call_args
  self.assertEqual(args[0],'https://imghost.dev/api/1/upload');self.assertEqual(kw['headers'],{'X-API-Key':'private-image-key'})
  self.assertIn('source',kw['files']);self.assertEqual(kw['files']['source'][2],'image/gif');self.assertFalse(kw['allow_redirects'])
  self.assertEqual(result['url'],'https://imghost.dev/images/test.gif')
 def test_existing_dirtybytes_contract(self):
  self.config.set('ImageHost','PROVIDER','dirtybytes')
  session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False)
  session.post.return_value=self.response({'data':{'link':'https://dirtybytes.net/images/cover.gif'}})
  with patch.object(image_host.requests,'Session',return_value=session):result=image_host.upload(self.config,'cover.gif',GIF)
  args,kw=session.post.call_args
  self.assertIn('/api/v1/images/upload',args[0]);self.assertIn('file',kw['files']);self.assertEqual(kw['headers']['X-API-KEY'],'private-site-key')
 def test_reject_invalid_images_and_size(self):
  for raw in (b'',b'<svg>bad</svg>',b'not an image',b'GIF89a'+b'x'*(image_host.MAX_IMAGE)):
   with self.assertRaises(ValueError):image_host.identify(raw)
 def test_no_key_or_reflected_secret_leak(self):
  self.config.set('ImageHost','PROVIDER','imghost');self.config.set('ImageHost','API_KEY','')
  with self.assertRaisesRegex(ValueError,'Settings'):image_host.post(self.config,'cover.gif',GIF)
  with patch.object(image_host,'post',return_value=self.response({'error':'private-image-key'},401)),self.assertRaises(ValueError) as error:
   image_host.upload(self.config,'cover.gif',GIF)
  self.assertNotIn('private-image-key',str(error.exception))
 def test_reject_bad_response_urls(self):
  self.assertEqual(image_host.image_url(self.response({'image':{'url':'javascript:alert(1)'}})),'')
  self.assertEqual(image_host.image_url(self.response({'image':{'url':'https://user:secret@example.com/a'}})),'')

class PublicDownloadTests(unittest.TestCase):
 def test_only_supported_catalogue_hosts_and_https(self):
  for url in ['http://www.jeedoo.com/','https://evil.invalid/','https://www.jeedoo.com:8443/','https://user:pass@www.jeedoo.com/']:
   with self.assertRaises(ValueError):public_download.validate_url(url,public_download.CATALOGUE_HOSTS)
 def test_private_dns_never_connects(self):
  with patch.object(public_download.socket,'getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]),patch.object(public_download,'PinnedHTTPS') as connection:
   with self.assertRaises(ValueError):public_download.download('https://www.jeedoo.com/')
   connection.assert_not_called()
 def test_tls_uses_pinned_address_and_original_hostname(self):
  context=Mock();sock=Mock()
  with patch.object(public_download.ssl,'create_default_context',return_value=context),patch.object(public_download.socket,'create_connection',return_value=sock) as connect:
   connection=public_download.PinnedHTTPS('www.jeedoo.com','93.184.216.34',20);connection.connect()
  connect.assert_called_once_with(('93.184.216.34',443),20)
  context.wrap_socket.assert_called_once_with(sock,server_hostname='www.jeedoo.com')
 def fake(self,status=200,body=b'<html>title</html>',location=''):
  response=Mock();response.status=status;response.read.return_value=body
  response.getheader.side_effect=lambda key: {'Content-Type':'text/html','Content-Length':str(len(body)),'Location':location}.get(key)
  connection=Mock();connection.getresponse.return_value=response
  return connection
 def test_bounded_download_and_no_auth_headers(self):
  connection=self.fake()
  with patch.object(public_download.socket,'getaddrinfo',return_value=[(0,0,0,'',('93.184.216.34',443))]),patch.object(public_download,'PinnedHTTPS',return_value=connection):
   result=public_download.catalogue_page('https://www.jeedoo.com/title/one')
  self.assertIn('title',result['html']);self.assertNotIn('Authorization',connection.request.call_args.kwargs['headers'])
  connection.close.assert_called_once()
 def test_redirect_to_private_or_unsupported_host_is_rejected(self):
  connection=self.fake(302,location='https://127.0.0.1/')
  with patch.object(public_download.socket,'getaddrinfo',return_value=[(0,0,0,'',('93.184.216.34',443))]),patch.object(public_download,'PinnedHTTPS',return_value=connection) as create:
   with self.assertRaises(ValueError):public_download.catalogue_page('https://www.jeedoo.com/title/one')
   self.assertEqual(create.call_count,1)
 def test_oversized_body_is_rejected(self):
  connection=self.fake(body=b'large file')
  with patch.object(public_download.socket,'getaddrinfo',return_value=[(0,0,0,'',('93.184.216.34',443))]),patch.object(public_download,'PinnedHTTPS',return_value=connection):
   with self.assertRaises(ValueError):public_download.download('https://example.com/a',limit=3)
