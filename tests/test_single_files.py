import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils.single_files import prepare
from utils.web_settings import defaults,schema,apply
from utils.torrent_metadata import TorrentMetadata
from utils.runtime_tools import find_tool

class SingleFileTests(unittest.TestCase):
 def setUp(self):
  (ROOT/'tmp').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp');self.root=Path(self.temp.name)
  self.library=self.root/'media';self.library.mkdir();self.file=self.library/'My.Release.2026.mkv';self.file.write_bytes(b'payload'*8192)
  self.config=defaults();self.config.set('Paths','DATADIR',str(self.library))
 def tearDown(self):self.temp.cleanup()
 def test_hardlink_is_one_payload_and_reused_without_overwriting(self):
  result=prepare(str(self.file),self.config);folder=Path(result['source']);target=folder/self.file.name
  self.assertEqual(folder.name,'My.Release.2026');self.assertTrue(target.samefile(self.file));self.assertFalse(target.is_symlink())
  self.assertFalse(prepare(str(self.file),self.config)['created']);self.assertEqual(self.file.read_bytes(),b'payload'*8192)
 @unittest.skipIf(os.name=='nt','Symlink creation needs Windows developer mode; exercised in Docker')
 def test_softlink_is_relative_and_resolves_from_another_mount_name(self):
  self.config.set('SingleFiles','LINK_MODE','softlink');result=prepare(str(self.file),self.config);target=Path(result['source'])/self.file.name
  self.assertTrue(target.is_symlink());self.assertFalse(Path(os.readlink(target)).is_absolute());self.assertTrue(target.samefile(self.file))
  moved=self.root/'another-mount';self.library.rename(moved)
  self.assertEqual((moved/'My.Release.2026'/self.file.name).read_bytes(),b'payload'*8192)
 def test_existing_release_is_not_overwritten(self):
  folder=self.library/self.file.stem;folder.mkdir();(folder/'existing.txt').write_text('preserve')
  with self.assertRaisesRegex(ValueError,'already exists'):prepare(str(self.file),self.config)
  self.assertEqual((folder/'existing.txt').read_text(),'preserve');self.assertTrue(self.file.exists())
 def test_outside_library_and_unsupported_mode_are_rejected(self):
  outside=self.root/'secret.mkv';outside.write_bytes(b'outside')
  with self.assertRaises(ValueError):prepare(str(outside),self.config)
  self.config.set('SingleFiles','LINK_MODE','copy')
  with self.assertRaises(ValueError):prepare(str(self.file),self.config)
  self.assertFalse((self.library/self.file.stem).exists())
 def test_link_failure_leaves_original_and_removes_only_empty_new_folder(self):
  with patch('utils.single_files.os.link',side_effect=OSError('cross device')):
   with self.assertRaisesRegex(ValueError,'Could not create'):prepare(str(self.file),self.config)
  self.assertTrue(self.file.exists());self.assertFalse((self.library/self.file.stem).exists())
 def test_modes_are_a_validated_settings_dropdown(self):
  section=next(s for s in schema(self.config) if s['section']=='SingleFiles');field=next(f for f in section['fields'] if f['key']=='link_mode')
  self.assertEqual(field['type'],'select');self.assertEqual({v['value'] for v in field['options']},{'hardlink','softlink'})
  apply(self.config,{'SingleFiles':{'link_mode':'softlink'}});self.assertEqual(self.config.get('SingleFiles','LINK_MODE'),'softlink')
  with self.assertRaises(ValueError):apply(self.config,{'SingleFiles':{'link_mode':'copy'}})
 @unittest.skipIf(os.name=='nt','Uses bundled Linux mkbrr and symlink support')
 def test_real_hasher_accepts_hardlinks_and_in_library_softlinks(self):
  from utils import torrent_utils
  self.config.set('Torrent','ANNOUNCEURL','https://example.invalid/announce/test');self.config.set('Torrent','ESOURCE','DCR')
  if not find_tool('mkbrr',self.config):self.skipTest('Bundled mkbrr required')
  for mode in ['hardlink','softlink']:
   original=self.library/(mode+'.mkv');original.write_bytes(b'payload'*8192);self.config.set('SingleFiles','LINK_MODE',mode)
   folder=Path(prepare(str(original),self.config)['source'])
   with patch.object(torrent_utils,'config',self.config):
    output,_=torrent_utils.create_torrent(folder,self.root/('tmp-'+mode),False,'mkbrr',original.stat().st_size)
   torrent=TorrentMetadata.read(output);self.assertEqual(torrent.file_sizes,[original.stat().st_size]);self.assertEqual(torrent.name,mode)
   self.assertTrue(torrent.verify_filesize(folder,allowed_root=self.library))
   if mode=='softlink':self.assertFalse(torrent.verify_filesize(folder))
