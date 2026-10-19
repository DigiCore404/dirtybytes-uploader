"""Existing-data reuse: mismatch paths must never start mkbrr or a download."""
import base64
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from torrent_fixtures import Torrent
from utils.source_torrent import validate, prepare
from utils.web_settings import defaults
import uploader
import web

class ExistingDataTests(unittest.TestCase):
    def setUp(self):
        initial_cwd=Path.cwd()
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir,initial_cwd)
        self.root=Path(self.temp.name);self.content=self.root/'content';self.content.mkdir()
        self.release=self.content/'Release';self.release.mkdir()
        self.video=self.release/'video.mp4';self.video.write_bytes(b'media payload')
        torrent=Torrent(self.release);torrent.generate();self.raw=torrent.dump()
        self.original=self.root/'original.torrent';self.original.write_bytes(self.raw)
        self.config=defaults();self.config.set('Paths','DATADIR',str(self.content))
        self.config.set('Paths','WATCHFOLDER',str(self.root/'watch'))
        self.config.set('Settings','SCREENSHOTS','false')
        self.config.set('Torrent','ANNOUNCEURL','https://example.invalid/announce')
        self.config.set('Torrent','SOURCEFOLDER',str(self.root/'missing'))
        category_rows=uploader.categories()
        self.cat=category_rows[0]['id']
        categories_patch=patch.object(uploader,'categories',return_value=category_rows)
        categories_patch.start();self.addCleanup(categories_patch.stop)
        for target,kwargs in [(patch.object(uploader,'load_config',return_value=self.config),{}),
                              (patch.object(uploader,'check_config',return_value=[]),{}),
                              (patch.object(uploader,'check_writable'),{})]:
            target.start();self.addCleanup(target.stop)
        self.workspace=web.Workspace('private',self.root/'history.db')
        # Keep original source metadata isolated from any real runtime data.
        self.root_patch=patch.object(uploader,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.data={'existing_data':True,'existing_path':str(self.release),'torrent':base64.b64encode(self.raw).decode(),
                   'category':self.cat,'metadata':{},'images':[],'description':'Existing pack'}

    def test_import_reuses_without_a_client_and_records_history(self):
        with patch.object(self.workspace.clients,'add_torrent') as download,patch.object(self.workspace.clients,'export_torrent') as export,patch.object(uploader,'run_job',return_value=0) as worker:
            result=self.workspace.imports.add(self.data)
            for _ in range(100):
                if self.workspace.active is None:break
                time.sleep(.01)
            download.assert_not_called();export.assert_not_called()
            job=worker.call_args.args[0]
            self.assertEqual(Path(job['source_torrent']).read_bytes(),self.raw)
            self.assertEqual(job['source'],str(self.release.resolve()))
            self.assertEqual(self.workspace.history.get(result['id'])['status'],'completed')
            row=self.workspace.imports.rows()[0]
            self.assertEqual(row['folder_layout'],'existing');self.assertEqual(row['seed_status'],'watch_folder')
            self.workspace.imports.seed_completed();download.assert_not_called()
            with self.assertRaisesRegex(ValueError,'already'):self.workspace.imports.add(self.data)

    def test_mismatch_does_not_download_dispatch_or_create_history(self):
        self.video.write_bytes(b'wrong size')
        with patch.object(uploader,'run_job') as worker,patch.object(self.workspace.clients,'add_torrent') as download:
            with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):self.workspace.imports.add(self.data)
            worker.assert_not_called();download.assert_not_called()
        self.assertEqual(self.workspace.imports.rows(),[])
        self.assertFalse((self.root/'data/import-torrents').exists())

    def test_missing_payload_stops(self):
        self.video.unlink()
        with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):validate(self.original,self.release)

    def test_renamed_root_allowed_inner_filename_must_match(self):
        renamed=self.content/'Different.Root';self.release.rename(renamed)
        validate(self.original,renamed)
        (renamed/'video.mp4').rename(renamed/'other.mp4')
        with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):validate(self.original,renamed)

    def test_single_file_validates_before_creating_release_folder(self):
        file=self.content/'Loose.mp4';file.write_bytes(b'content')
        torrent=Torrent(file);torrent.generate();self.original.write_bytes(torrent.dump())
        wrong=self.content/'Other.mp4';wrong.write_bytes(b'content')
        with self.assertRaisesRegex(ValueError,'file name'):
            uploader.validate_job(wrong,self.cat,config=self.config,source_torrent=self.original)
        self.assertFalse((self.content/'Other').exists())
        job=uploader.validate_job(file,self.cat,config=self.config,source_torrent=self.original)
        validate(self.original,job['source'],allowed_root=self.content)
        self.assertTrue((Path(job['source'])/'Loose.mp4').samefile(file))

    def test_multifile_cannot_be_matched_to_a_single_file(self):
        with self.assertRaises(ValueError):validate(self.original,self.video)

    def test_existing_data_rejects_magnet_or_library_root(self):
        for changes in ({'torrent':'','magnet':'magnet:?xt=urn:btih:'+'a'*40},{'existing_path':str(self.content)}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.workspace.imports.add(dict(self.data,**changes))

    def test_files_changed_after_review_do_not_dispatch(self):
        review=self.workspace.review(dict(self.data,source=str(self.release)),source_torrent=self.original)
        self.video.write_bytes(b'changed')
        with patch.object(uploader,'run_job') as worker:
            with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):self.workspace.upload(review['review_id'])
            worker.assert_not_called()

    def test_builder_never_falls_back_for_missing_mismatched_or_excluded_torrent(self):
        import utils.torrent_utils as tu
        self.video.write_bytes(b'changed')
        with patch.object(tu,'config',self.config),patch('utils.runtime_tools.find_tool',return_value='mkbrr'),patch.object(tu.subprocess,'Popen') as process:
            for kwargs in ({'source_torrent':self.root/'absent.torrent'}, {'source_torrent':self.original}, {'edit':True},
                           {'source_torrent':self.original,'exclude_globs':['*.mp4']}):
                args=dict(edit=False,hasher='mkbrr');args.update(kwargs)
                with self.subTest(args=args),self.assertRaisesRegex(ValueError,'[Nn]o rehash'):
                    tu.create_torrent(self.release,self.root/'output',**args)
            process.assert_not_called()

    def test_legacy_cli_forwards_torrent_and_stops_on_mismatch(self):
        with patch.object(uploader,'ensure_config'),patch.object(uploader,'run_job',return_value=0) as worker:
            self.assertEqual(uploader.run_backend_cli([str(self.release),'--cat',str(self.cat),'--torrent',str(self.original)]),0)
            self.assertEqual(worker.call_args.args[0]['source_torrent'],str(self.original))
            self.video.unlink();worker.reset_mock()
            with self.assertRaisesRegex(ValueError,'[Nn]o rehash'):
                uploader.run_backend_cli([str(self.release),'--cat',str(self.cat),'--torrent',str(self.original)])
            worker.assert_not_called()

    def test_docker_helper_mounts_original_readonly(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('reuse_docker',ROOT/'docker-run.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        command=module.command(['upload',str(self.release),'--torrent',str(self.original)],self.config)
        self.assertIn('type=bind,source='+str(self.original.resolve())+',target=/source/original.torrent,readonly',command)
        self.assertIn('/source/original.torrent',command)

    @unittest.skipUnless(os.name=='posix','POSIX symlinks')
    def test_symlink_cannot_escape_content_root(self):
        outside=self.root/'outside.mp4';outside.write_bytes(self.video.read_bytes())
        self.video.unlink();self.video.symlink_to(outside)
        with self.assertRaises(ValueError):self.workspace.imports.add(self.data)

    @unittest.skipUnless(os.name=='posix','POSIX symlinks')
    def test_reused_single_file_softlink_within_library(self):
        file=self.content/'Soft.mp4';file.write_bytes(b'payload')
        torrent=Torrent(file);torrent.generate();self.original.write_bytes(torrent.dump())
        self.config.set('SingleFiles','LINK_MODE','softlink')
        job=uploader.validate_job(file,self.cat,config=self.config,source_torrent=self.original)
        prepare(self.original,job['source'],self.root/'prepared.torrent',allowed_root=self.content)
        self.assertTrue((Path(job['source'])/file.name).is_symlink())

    def test_packed_torrent_stops_instead_of_unpacking_and_hashing(self):
        (self.release/'archive.rar').write_bytes(b'packed source')
        torrent=Torrent(self.release);torrent.generate();self.original.write_bytes(torrent.dump())
        with self.assertRaisesRegex(ValueError,'No rehash'):
            uploader.validate_job(self.release,self.cat,config=self.config,source_torrent=self.original)
