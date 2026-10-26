import configparser
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import torrent_exclusions as exclusions
from utils.web_settings import defaults, schema, apply
import uploader


class ExclusionTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).resolve().parents[1]/'tmp';scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root/'Release'
        self.release.mkdir()
        (self.release/'video.mkv').write_bytes(b'video' * 10000)
        (self.release/'spam.NFO').write_text('advertisement')
        (self.release/'nested').mkdir()
        (self.release/'nested'/'other.txt').write_text('advertisement')
        self.config = defaults()
        self.config.set('Paths','DATADIR',str(self.root))
        self.config.set('Torrent','EXCLUDE_PATTERNS','*.nfo, *.txt')
        self.config.set('Torrent','ANNOUNCEURL','https://tracker.example/announce/test')

    def test_nested_case_insensitive_names_and_relative_globs(self):
        patterns = exclusions.patterns(self.config)
        self.assertTrue(exclusions.matches('nested/INFO.NFO', patterns))
        self.assertTrue(exclusions.matches('nested/other.txt', patterns))
        self.assertFalse(exclusions.matches('video.mkv', patterns))
        self.assertTrue(exclusions.matches('Sample/preview.jpg', ['Sample/*.jpg']))
        self.assertFalse(exclusions.matches('Covers/preview.jpg', ['Sample/*.jpg']))

    def test_setting_is_editable_and_invalid_absolute_patterns_rejected(self):
        fields = next(s['fields'] for s in schema(self.config) if s['section']=='Torrent')
        self.assertIn('exclude_patterns',[f['key'] for f in fields])
        apply(self.config,{'Torrent':{'exclude_patterns':'*.nfo, *.txt'}})
        with self.assertRaises(ValueError):
            apply(self.config,{'Torrent':{'exclude_patterns':'../*'}})

    def test_dry_review_preserves_source_and_shows_patterns(self):
        before = {str(p):p.read_bytes() for p in self.release.rglob('*') if p.is_file()}
        category = uploader.categories()[0]['id']
        job = uploader.validate_job(self.release,category,config=self.config,prepare_files=False)
        self.assertIn('Torrent exclusions: *.nfo, *.txt',uploader.review_text(job,self.config))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.release.rglob('*') if p.is_file()})

    def test_empty_payload_and_reuse_stop_before_any_hasher(self):
        with patch('utils.config_loader.ConfigLoader.__init__',return_value=None),patch('utils.config_loader.ConfigLoader.get_config',return_value=self.config):
            from utils import torrent_utils
        with patch.object(torrent_utils,'config',self.config),patch('utils.runtime_tools.find_tool',return_value='mkbrr'),patch.object(torrent_utils.subprocess,'Popen') as process:
            with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):
                torrent_utils.create_torrent(self.release,self.root/'out',False,'mkbrr',source_torrent=self.root/'existing.torrent')
            self.config.set('Torrent','EXCLUDE_PATTERNS','*')
            with self.assertRaisesRegex(ValueError,'every file'):
                torrent_utils.create_torrent(self.release,self.root/'out',False,'mkbrr')
            process.assert_not_called()

    @unittest.skipIf(os.name=='nt','Bundled mkbrr runs on Linux')
    def test_real_mkbrr_hashes_only_media_and_preserves_source_files(self):
        with patch('utils.config_loader.ConfigLoader.__init__',return_value=None),patch('utils.config_loader.ConfigLoader.get_config',return_value=self.config):
            from utils import torrent_utils
        from utils.torrent_metadata import TorrentMetadata
        before = {str(p):p.read_bytes() for p in self.release.rglob('*') if p.is_file()}
        with patch.object(torrent_utils,'config',self.config):
            output,_ = torrent_utils.create_torrent(self.release,self.root/'out',False,'mkbrr')
        torrent = TorrentMetadata.read(output)
        self.assertEqual([p.name for p in torrent.files],['video.mkv'])
        self.assertEqual(sum(torrent.file_sizes),(self.release/'video.mkv').stat().st_size)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.release.rglob('*') if p.is_file()})
