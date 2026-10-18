from pathlib import Path
import configparser
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.screenshot_batch import generate_batch
from utils.web_settings import defaults, schema, apply
from utils.screenshot_utils import generate_candidate

class ScreenshotBatchTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.root = Path(self.temp.name)
        self.media = self.root / 'pack'
        self.media.mkdir()
        self.config = defaults()
        self.config.set('Paths', 'TMP_DIR', str(self.root / 'tmp'))
        self.config.set('MediaTools', 'SCREENSHOT_VIDEO_MODE', 'all')
        self.target = self.root / 'tmp' / str(os.getpid()) / 'screens'
    def tearDown(self):
        self.temp.cleanup()
    def video(self, name, data=b'video'):
        p = self.media / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p
    def capture(self, source, target, config):
        for suffix in ('sheet', '01'):
            (target / (source.stem + '-' + suffix + '.jpg')).write_bytes(source.read_bytes() + suffix.encode())
    def test_all_videos_nested_names_are_unique_and_samples_excluded(self):
        self.video('a/video.mp4', b'first')
        self.video('b/video.mp4', b'second')
        self.video('samples/sample.mp4')
        generate_batch(self.media, self.config, self.capture)
        files = list(self.target.glob('*.jpg'))
        self.assertEqual(len(files), 4)
        self.assertEqual(len(list(self.target.glob('*-sheet.jpg'))), 2)
        self.assertEqual(len({p.read_bytes() for p in files}), 4)
    def test_single_tries_next_main_without_leaking_failed_images(self):
        self.config.set('MediaTools', 'SCREENSHOT_VIDEO_MODE', 'single')
        self.video('first.mp4', b'large first')
        self.video('second.mp4', b'ok')
        seen = []
        def capture(source, target, config):
            seen.append(source.name)
            (target / 'frame.jpg').write_bytes(source.read_bytes())
            if len(seen) == 1:
                raise RuntimeError('broken video')
        generate_batch(self.media, self.config, capture)
        self.assertEqual(seen, ['first.mp4', 'second.mp4'])
        self.assertEqual([p.read_bytes() for p in self.target.glob('*.jpg')], [b'ok'])
    def test_all_failure_preserves_completed_previews_and_stops_by_default(self):
        self.video('good.mp4', b'large good video')
        self.video('bad.mp4', b'bad')
        def capture(source, target, config):
            if source.name == 'bad.mp4':
                (target / 'partial.jpg').write_bytes(b'bad')
                raise RuntimeError('broken video')
            self.capture(source, target, config)
        with self.assertRaisesRegex(RuntimeError, 'bad.mp4'):
            generate_batch(self.media, self.config, capture)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 2)
        self.config.set('Settings', 'REQUIRE_SCREENSHOTS', 'false')
        generate_batch(self.media, self.config, capture)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 2)
    def test_sample_only_fallback_is_optional(self):
        self.video('samples/sample.mp4')
        self.config.set('Settings', 'SCREENSHOT_SAMPLE_FALLBACK', 'false')
        generate_batch(self.media, self.config, self.capture)
        self.assertFalse(self.target.exists())
        self.config.set('Settings', 'SCREENSHOT_SAMPLE_FALLBACK', 'true')
        generate_batch(self.media, self.config, self.capture)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 2)
    def test_settings_roundtrip_for_web_and_cli(self):
        self.assertEqual(defaults().get('MediaTools', 'SCREENSHOT_VIDEO_MODE'), 'single')
        field = next(f for s in schema(self.config) for f in s['fields'] if f['key'] == 'screenshot_video_mode')
        self.assertEqual(field['type'], 'select')
        self.assertEqual({o['value'] for o in field['options']}, {'single', 'all'})
        apply(self.config, {'MediaTools': {'screenshot_video_mode': 'all'}})
        path = self.root / 'config.ini'
        with path.open('w') as stream:
            self.config.write(stream)
        loaded = configparser.ConfigParser(interpolation=None)
        loaded.read(path)
        self.assertEqual(loaded.get('MediaTools', 'SCREENSHOT_VIDEO_MODE'), 'all')
        with self.assertRaises(ValueError):
            apply(self.config, {'MediaTools': {'screenshot_video_mode': 'invalid'}})
    def test_real_pack_sheets_and_frames_for_every_video(self):
        from utils.runtime_tools import find_tool
        if not find_tool('mtn', self.config):
            self.skipTest('Native MTN required')
        for folder, pattern in [('a', 'testsrc2'), ('b', 'smptebars')]:
            video = self.video(folder + '/video.mp4')
            video.unlink()
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', pattern + '=size=640x360:rate=5:duration=24', '-c:v', 'mpeg4', str(video)], check=True)
        self.config.set('MediaTools', 'SCREENSHOT_ENGINE', 'mtn')
        self.config.set('MediaTools', 'SCREENSHOT_SHEET', 'true')
        self.config.set('MediaTools', 'SCREENSHOT_SINGLES', '1')
        generate_batch(self.media, self.config, generate_candidate)
        files = list(self.target.glob('*.jpg'))
        self.assertEqual(len(files), 4)
        self.assertEqual(len(list(self.target.glob('*-sheet.jpg'))), 2)
        self.assertTrue(all(p.read_bytes().startswith(b'\xff\xd8') for p in files))
        self.assertEqual(len({hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), 4)
        self.config.set('MediaTools', 'SCREENSHOT_ENGINE', 'ffmpeg')
        generate_batch(self.media, self.config, generate_candidate)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 2)


import test_uploader as fixtures
class PackPublicationTests(unittest.TestCase):
    setUp = fixtures.UploaderTests.setUp
    tearDown = fixtures.UploaderTests.tearDown
    serve = fixtures.UploaderTests.serve
    job = fixtures.UploaderTests.job
    def test_cli_backend_publishes_sheets_and_frames_from_both_videos(self):
        import uploader
        from utils.runtime_tools import find_tool
        if not find_tool('mkbrr', self.config) or not find_tool('mtn', self.config):
            self.skipTest('Native mkbrr and MTN required')
        state = self.serve()
        category = self.job()['category']
        for folder, pattern in [('a', 'testsrc2'), ('b', 'smptebars')]:
            path = self.release / folder / 'video.mp4'
            path.parent.mkdir()
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', pattern + '=size=640x360:rate=5:duration=24', '-c:v', 'mpeg4', str(path)], check=True)
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.cfg)
        config.set('Settings', 'SCREENSHOTS', 'true')
        config.set('Settings', 'SCREENSHOT_CATEGORIES', str(category))
        config.add_section('MediaTools')
        for key, value in {'SCREENSHOT_VIDEO_MODE':'all', 'SCREENSHOT_ENGINE':'mtn', 'SCREENSHOT_SHEET':'true', 'SCREENSHOT_SINGLES':'1'}.items():
            config.set('MediaTools', key, value)
        with self.cfg.open('w') as stream:
            config.write(stream)
        config = uploader.load_config()
        output = []
        self.assertEqual(uploader.run_job(self.job(), config, output.append), 0, '\n'.join(output))
        self.assertEqual(state['images'], 4)
        self.assertIn('https://example.invalid/uploaded.jpg', state['posts'][0]['nfo'])
