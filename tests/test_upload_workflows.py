"""End-to-end contracts for drafts, privacy, native files and confirmed delivery."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import uploader
from utils.web_settings import defaults
from utils.job_history import JobHistory
from utils.upload_drafts import DraftStore
from utils.publication_identity import resolve_anonymity
from utils.delivery_queue import DeliveryQueue
from utils.torrent_metadata import TorrentMetadata, decode
from utils.single_files import prepare

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  (ROOT/'tmp').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.media=self.root/'media';self.media.mkdir();self.file=self.media/'Film.2026.mkv';self.file.write_bytes(b'payload'*8192)
  self.config=defaults()
  for key,value in [('DATADIR',self.media),('TMP_DIR',self.root/'scratch'),('WATCHFOLDER',self.root/'watch'),('TEMPLATE_PATH',ROOT/'files/template.txt')]:self.config.set('Paths',key,str(value))
  self.config.set('Settings','SCREENSHOTS','false');self.config.set('Settings','MEDIAINFO','false')
  self.config.set('SingleFiles','CREATE_RELEASE_FOLDER','false')
  self.config.set('Website','SITEURL','https://example.invalid')
  self.config.set('Torrent','ANNOUNCEURL','https://example.invalid/announce/test');self.config.set('Torrent','ESOURCE','TEST')
  self.category=uploader.categories()[0]['id'];self.history=JobHistory(self.root/'history.db')
 def test_file_selection_and_dry_review_never_stage_media(self):
  self.config.set('SingleFiles','CREATE_RELEASE_FOLDER','true')
  before=set(self.media.iterdir())
  selected=prepare(str(self.file),self.config,create=False)
  job=uploader.validate_job(self.file,self.category,config=self.config,prepare_files=False)
  self.assertEqual(job['source'],str(self.file));self.assertEqual(job['release_name'],'Film.2026')
  self.assertEqual(selected['source'],str(self.file));self.assertEqual(set(self.media.iterdir()),before)
 def test_native_torrent_keeps_filename_and_uses_extensionless_output_title(self):
  if os.name=='nt':self.skipTest('Bundled Linux mkbrr is tested in Docker')
  from utils import torrent_utils
  with patch.object(torrent_utils,'config',self.config):
   output,_=torrent_utils.create_torrent(self.file,self.root/'hash',False,'mkbrr',self.file.stat().st_size)
  metadata=TorrentMetadata.read(output)
  self.assertEqual(metadata.name,self.file.name);self.assertEqual(Path(output).name,'Film.2026.torrent')
  self.assertTrue(metadata.verify_filesize(self.file,allowed_root=self.media));self.assertFalse((self.media/self.file.stem).exists())
 def test_native_existing_torrent_reuses_pieces_without_reading_or_rehashing(self):
  if os.name=='nt':self.skipTest('Linux permissions and bundled mkbrr are tested in Docker')
  from torrent_fixtures import Torrent
  from utils import torrent_utils
  original=Torrent(self.file);original.generate();path=self.root/'original.torrent';path.write_bytes(original.dump())
  before=TorrentMetadata.read(path);self.file.chmod(0)
  try:
   with patch.object(torrent_utils,'config',self.config):
    output,_=torrent_utils.create_torrent(self.file,self.root/'reuse',False,'mkbrr',self.file.stat().st_size,source_torrent=path)
   after=TorrentMetadata.read(output)
   after_info=decode(after.raw)[0][b'info'];before_info=decode(before.raw)[0][b'info']
   self.assertEqual(after_info[b'pieces'],before_info[b'pieces']);self.assertIn(b'length',after_info);self.assertNotIn(b'files',after_info)
   self.assertEqual(after.name,self.file.name)
  finally:self.file.chmod(0o600)
 def test_persistent_draft_preview_never_calls_site_or_creates_media_folders(self):
  store=DraftStore(SimpleNamespace(history=self.history))
  with patch.object(uploader,'load_config',return_value=self.config),patch('requests.sessions.Session.request',side_effect=AssertionError('Preview must not publish')):
   draft=store.save({'source':str(self.file),'post_title':'Edited site title','description':'A saved draft'})
   self.assertEqual(draft['payload']['post_title'],'Edited site title');self.assertEqual(draft['payload']['release_name'],'Film.2026');self.assertIsNone(draft['payload']['category'])
   with self.assertRaises(ValueError):store.preview(draft['id'])
   draft=store.save(dict(draft['payload'],draft_id=draft['id'],category=self.category))
   store.preview(draft['id']);store.preview_thread.join(15)
   row=store.get(draft['id']);self.assertEqual(row['state'],'ready',row['error']);self.assertIn('A saved draft',row['preview']['description'])
   reopened=DraftStore(SimpleNamespace(history=self.history));self.assertEqual(reopened.get(draft['id'])['payload']['description'],'A saved draft')
   self.assertEqual(set(self.media.iterdir()),{self.file})
   changed=store.save(dict(row['payload'],draft_id=row['id'],description='Edited'))
   self.assertEqual(changed['state'],'saved');self.assertEqual(changed['preview'],{})
 def test_real_ffmpeg_preview_is_local_and_images_survive_restart(self):
  if os.name=='nt':self.skipTest('Media tools run in Docker')
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=12','-t','3','-c:v','libx264',str(self.file)],check=True,timeout=30)
  self.config.set('Settings','SCREENSHOTS','true');self.config.set('Settings','SCREENSHOT_CATEGORIES',str(self.category))
  self.config.set('MediaTools','SCREENSHOT_ENGINE','ffmpeg');self.config.set('MediaTools','SCREENSHOT_SINGLES','2')
  store=DraftStore(SimpleNamespace(history=self.history))
  with patch.object(uploader,'load_config',return_value=self.config),patch('requests.sessions.Session.request',side_effect=AssertionError('Preview must not upload images')):
   draft=store.save({'source':str(self.file),'category':self.category});store.preview(draft['id']);store.preview_thread.join(30)
  row=store.get(draft['id']);self.assertEqual(row['state'],'ready',row['error']);self.assertEqual(len(row['preview']['images']),2)
  reopened=DraftStore(SimpleNamespace(history=self.history));name=row['preview']['images'][0]['name']
  self.assertTrue(reopened.image(row['id'],row['revision'],name).startswith(b'\xff\xd8'))
  with self.assertRaises(ValueError):reopened.image(row['id'],row['revision'],'../secret.jpg')
 def test_privacy_reads_account_preference_and_fails_closed(self):
  response=Mock();response.json.return_value={'anonym':'yes'}
  with patch('utils.publication_identity.requests.get',return_value=response) as get:
   self.assertEqual(resolve_anonymity(self.config,{'X-API-Key':'private'}),1)
   self.assertTrue(get.call_args.args[0].endswith('/upload-preferences'));self.assertFalse(get.call_args.kwargs['allow_redirects'])
   response.json.return_value={'anonym':'no'};self.assertEqual(resolve_anonymity(self.config,{}),0)
   response.json.return_value={}
   with self.assertRaisesRegex(ValueError,'Upload stopped'):resolve_anonymity(self.config,{})
  for mode,expected in [('anonymous',1),('named',0)]:
   self.config.set('UploadForm','ANONYMITY',mode)
   with patch('utils.publication_identity.requests.get') as get:
    self.assertEqual(resolve_anonymity(self.config,{}),expected);get.assert_not_called()
  self.config.set('UploadForm','ANONYMITY','account');self.config.set('UploadForm','ANONYMOUS','1')
  from utils.web_settings import schema
  field=next(f for section in schema(self.config) for f in section['fields'] if f['key']=='anonymity')
  self.assertEqual(field['value'],'anonymous')
  with patch('utils.publication_identity.requests.get') as get:self.assertEqual(resolve_anonymity(self.config,{}),1);get.assert_not_called()
 def test_confirmed_delivery_retries_only_client_and_preserves_native_save_path(self):
  from torrent_fixtures import Torrent
  torrent=Torrent(self.file);torrent.generate();watch=Path(self.config.get('Paths','WATCHFOLDER'));watch.mkdir()
  path=watch/'confirmed.torrent';path.write_bytes(torrent.dump());metadata=TorrentMetadata.read(path)
  self.config.add_section('Delivery') if not self.config.has_section('Delivery') else None
  self.config.add_section('Imports') if not self.config.has_section('Imports') else None
  self.config.set('Delivery','MODE','client');self.config.set('Imports','CLIENT_ID','chosen');self.config.set('Imports','LOCAL_ROOT',str(self.media));self.config.set('Imports','REMOTE_ROOT','/downloads')
  clients=Mock();clients.import_status.side_effect=[RuntimeError('offline'),(None,[])]
  queue=DeliveryQueue(self.history,clients);events={'watch_torrent':str(path),'torrent_hash':metadata.infohash}
  result=queue.enqueue({'source':str(self.file)},self.config,events);self.assertEqual(result['state'],'pending');clients.add_torrent.assert_not_called()
  queue.tick();clients.add_torrent.assert_called_once_with('chosen',metadata.infohash,'/downloads',raw=metadata.raw,use_default_category=True)
  with self.history.connect() as db:self.assertEqual(db.execute('SELECT state FROM confirmed_deliveries').fetchone()[0],'added')
  clients.add_torrent.reset_mock();queue.tick();clients.add_torrent.assert_not_called()
  events['torrent_hash']='0'*40
  with self.assertRaisesRegex(ValueError,'hash'):queue.enqueue({'source':str(self.file)},self.config,events)
 def test_changelog_uses_fixed_release_url_and_explicit_fallback(self):
  from utils.update_check import changelog
  from utils.app_version import VERSION
  self.assertIn('## '+VERSION+' ',(ROOT/'CHANGELOG.md').read_text(encoding='utf-8'))
  response=Mock(status_code=200,text='# New history',content=b'# New history')
  with patch('utils.update_check.requests.get',return_value=response) as get:
   result=changelog(ROOT,'999.0.0');self.assertEqual(result['text'],'# New history');self.assertIn('/v999.0.0/CHANGELOG.md',get.call_args.args[0])
   response.status_code=404;self.assertIn('could not be retrieved',changelog(ROOT,'999.0.0')['notice'])
   with self.assertRaises(ValueError):changelog(ROOT,'../../untrusted')

if __name__=='__main__':unittest.main()
