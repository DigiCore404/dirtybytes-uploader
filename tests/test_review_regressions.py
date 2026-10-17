import sqlite3
import configparser
import os
import subprocess
import sys
import shutil
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import uploader
import test_uploader as fixtures
ROOT = fixtures.ROOT


class ReviewRegressionTests(unittest.TestCase):
    setUp = fixtures.UploaderTests.setUp
    tearDown = fixtures.UploaderTests.tearDown
    serve = fixtures.UploaderTests.serve
    job = fixtures.UploaderTests.job

    def watch_attempts(self, results):
        (self.root / 'files').mkdir()
        for path in (ROOT / 'files').glob('*-categories.json'):
            shutil.copyfile(path, self.root / 'files' / path.name)
        category = self.job()['category']
        with patch.object(uploader, 'ROOT', self.root), \
             patch.object(uploader.time, 'monotonic', side_effect=range(0, 1000, 10)), \
             patch.object(uploader.time, 'sleep', side_effect=[None, None, None, KeyboardInterrupt]), \
             patch.object(uploader, 'run_job', side_effect=results) as run:
            uploader.watch(self.config, category, interval=5, stable=5)
        with closing(sqlite3.connect(self.root / 'data/watch.db')) as db:
            return run.call_count, db.execute('SELECT status FROM jobs').fetchall()

    def test_busy_watcher_retries_only_before_worker_starts(self):
        count, rows = self.watch_attempts([uploader.UploadBusyError('busy'), 0])
        self.assertEqual(count, 2)
        self.assertEqual(rows, [('finished',)])

    def test_worker_error_requires_review_and_never_reposts(self):
        count, rows = self.watch_attempts([ValueError('failure after publication')])
        self.assertEqual(count, 1)
        self.assertEqual(rows, [('needs_review',)])

    def test_upload_conflict_prepares_seeding_but_records_duplicate(self):
        from utils.runtime_tools import find_tool
        if not find_tool('mkbrr', self.config):
            self.skipTest('Native mkbrr required for end-to-end upload')
        self.serve('upload-duplicate')
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.cfg)
        config.set('Settings', 'DUPEDL', 'true')
        with self.cfg.open('w') as stream:
            config.write(stream)
        self.config = uploader.load_config()
        output = []
        self.assertEqual(uploader.run_job(self.job(), self.config, output.append), 10, '\n'.join(output))
        self.assertEqual(len(list((self.root / 'watch').glob('*.torrent'))), 1)
        with closing(sqlite3.connect(ROOT / 'data/uploads.db')) as db:
            row = db.execute('SELECT status,site_status FROM upload_jobs ORDER BY started DESC LIMIT 1').fetchone()
        self.assertEqual(row, ('duplicate', 'duplicate'))

    def test_empty_unrar_suffix_never_reuses_original_release_name(self):
        from utils import unrar_upload_utils as unrar
        from utils.web_settings import defaults
        config = defaults()
        config.set('UnrarUpload', 'TITLE_SUFFIX', '')
        with patch.object(unrar, 'config', config):
            self.assertEqual(unrar.unrar_release_name('Test.Release'), 'Test.Release [UNRAR]')

    def test_template_roundtrip_is_utf8(self):
        from utils.template_utils import load_template, save_template
        path = self.root / 'template.txt'
        text = 'Release café 日本語 🎬'
        save_template(text, path)
        self.assertEqual(path.read_bytes(), text.encode('utf-8'))
        self.assertEqual(load_template(path), text)

    def test_nonobject_metadata_is_rejected_before_upload(self):
        for metadata in ([], ['bad'], 'bad', 42):
            with self.subTest(metadata=metadata), self.assertRaisesRegex(ValueError, 'Metadata must be an object'):
                self.job(metadata=metadata)

    def test_unexpected_backend_error_clears_uploading_and_records_failed(self):
        code = '''import sys
import uploader
uploader.check_writable(uploader.load_config())
from utils.database_utils import initialize_upload_database
initialize_upload_database()
import backend
def fail(*args, **kwargs):
    raise ValueError('ambiguous category fixture')
backend.determine_category = fail
sys.argv = ['backend.py', sys.argv[1], '--cat', sys.argv[2]]
backend.main()
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.release), str(self.job()['category'])],
                                cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue((self.release / '.failed').is_dir())
        self.assertFalse((self.release / '.uploading').exists())
        with closing(sqlite3.connect(ROOT / 'data/uploads.db')) as db:
            row = db.execute('SELECT status FROM uploads WHERE name=? ORDER BY id DESC LIMIT 1',
                             (self.release.name,)).fetchone()
        self.assertEqual(row, ('failed',))

    def test_generated_screenshots_upload_when_folder_image_upload_is_off(self):
        from utils.runtime_tools import find_tool
        if not find_tool('mkbrr', self.config):
            self.skipTest('Native mkbrr required for end-to-end upload')
        state = self.serve()
        category = self.job()['category']
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.cfg)
        config.set('Settings', 'SCREENSHOTS', 'true')
        config.set('Settings', 'SCREENSHOT_CATEGORIES', str(category))
        with self.cfg.open('w') as stream:
            config.write(stream)
        code = '''import sys,os,base64
from pathlib import Path
import uploader
config=uploader.load_config()
uploader.check_writable(config)
from utils.database_utils import initialize_upload_database
initialize_upload_database()
import backend
def screenshots(*args):
    folder=Path(config.get('Paths','TMP_DIR'))/str(os.getpid())/'screens'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'frame.gif').write_bytes(base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'))
backend.generate_screenshots=screenshots
sys.argv=['backend.py',sys.argv[1],'--cat',sys.argv[2]]
backend.main()
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.release), str(category)], cwd=ROOT,
                                env=os.environ.copy(), capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state['images'], 1)
        self.assertIn('https://example.invalid/uploaded.jpg', state['posts'][0]['nfo'])
