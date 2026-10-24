"""Total release caps exercise real batch and engine code without publishing."""
import configparser
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.screenshot_batch import generate_batch
from utils.screenshot_utils import generate_candidate
from utils.web_settings import defaults, schema, apply


class ScreenshotLimitTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'pack'
        self.media.mkdir()
        for i in range(5):
            (self.media / f'video-{i}.mp4').write_bytes(b'fixture')
        self.config = defaults()
        self.config.set('Paths', 'TMP_DIR', str(self.root / 'tmp'))
        self.config.set('MediaTools', 'SCREENSHOT_VIDEO_MODE', 'all')
        self.config.set('MediaTools', 'MTNBIN', '')
        self.config.set('MediaTools', 'SCREENSHOT_SINGLES', '3')
        self.target = self.root / 'tmp' / str(os.getpid()) / 'screens'
        self.probes = []
        self.frames = []

    def run_tool(self, command, **kwargs):
        if command[0] == 'ffprobe':
            self.probes.append(command[-1])
            return SimpleNamespace(stdout='{"format":{"duration":"24"}}')
        if command[0] == 'ffmpeg':
            output = Path(command[-1])
        else:
            source = Path(command[-1])
            output = Path(command[command.index('-O') + 1]) / (source.stem + command[command.index('-o') + 1])
        self.frames.append(str(output))
        output.write_bytes(b'\xff\xd8fixture\xff\xd9')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def generate(self, engine, limit):
        self.config.set('MediaTools', 'SCREENSHOT_ENGINE', engine)
        self.config.set('MediaTools', 'SCREENSHOT_LIMIT', str(limit))
        self.probes.clear()
        self.frames.clear()
        with patch('utils.screenshot_utils.subprocess.run', side_effect=self.run_tool), patch('utils.mtn_screenshots.find_tool', return_value='/mock/mtn'):
            generate_batch(self.media, self.config, generate_candidate)
        return list(self.target.glob('*.jpg'))

    def test_exact_caps_stop_both_engines_before_later_videos(self):
        for engine in ['ffmpeg', 'mtn']:
            for limit in [1, 5, 10]:
                with self.subTest(engine=engine, limit=limit):
                    files = self.generate(engine, limit)
                    self.assertEqual(len(files), limit)
                    self.assertEqual(len(self.frames), limit, 'Do not generate then discard extra frames')
                    per_video = 4 if engine == 'mtn' else 3
                    self.assertEqual(len(self.probes), (limit + per_video - 1) // per_video)
                    if engine == 'mtn':
                        self.assertEqual(sum(p.name.endswith('-sheet.jpg') for p in files), len(self.probes))
                    self.assertEqual(self.config.getint('MediaTools', 'SCREENSHOT_SINGLES'), 3)

    def test_zero_preserves_all_videos_and_missing_option_is_compatible(self):
        self.assertEqual(len(self.generate('ffmpeg', 0)), 15)
        self.assertEqual(len(self.generate('mtn', 0)), 20)
        self.config.remove_option('MediaTools', 'SCREENSHOT_LIMIT')
        with patch('utils.screenshot_utils.subprocess.run', side_effect=self.run_tool), patch('utils.mtn_screenshots.find_tool', return_value='/mock/mtn'):
            generate_batch(self.media, self.config, generate_candidate)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 20)

    def test_mtn_without_sheets_and_limit_above_available(self):
        self.config.set('MediaTools', 'SCREENSHOT_SHEET', 'false')
        self.assertEqual(len(self.generate('mtn', 5)), 5)
        self.assertFalse(any(p.name.endswith('-sheet.jpg') for p in self.target.glob('*.jpg')))
        self.assertEqual(len(self.generate('mtn', 100)), 15)

    def test_failures_do_not_consume_budget_or_bypass_required_checks(self):
        self.config.set('MediaTools', 'SCREENSHOT_LIMIT', '1')
        def capture(source, target, config):
            (target / 'frame.jpg').write_bytes(b'frame')
            if source.name == 'video-0.mp4':
                raise RuntimeError('Broken video')
        with self.assertRaisesRegex(RuntimeError, 'video-0.mp4'):
            generate_batch(self.media, self.config, capture)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 1)
        self.config.set('MediaTools', 'SCREENSHOT_VIDEO_MODE', 'single')
        generate_batch(self.media, self.config, capture)
        self.assertEqual(len(list(self.target.glob('*.jpg'))), 1)

    def test_web_settings_validation_and_cli_roundtrip(self):
        self.assertEqual(defaults().getint('MediaTools', 'SCREENSHOT_LIMIT'), 0)
        field = next(f for group in schema(self.config) for f in group['fields'] if f['key'] == 'screenshot_limit')
        self.assertEqual(field['type'], 'number')
        for count in [0, 5, 10, "5.0"]:
            apply(self.config, {'MediaTools': {'screenshot_limit': str(count)}})
            path = self.root / 'config.ini'
            with path.open('w', encoding='utf-8') as stream:
                self.config.write(stream)
            loaded = configparser.ConfigParser(interpolation=None)
            loaded.read(path, encoding='utf-8')
            self.assertEqual(loaded.getint('MediaTools', 'SCREENSHOT_LIMIT'), int(float(count)))
        for value in ['-1', '2.5', 'NaN', '10001', 'invalid']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply(self.config, {'MediaTools': {'screenshot_limit': value}})
        self.config.set('MediaTools', 'SCREENSHOT_LIMIT', '-1')
        with self.assertRaisesRegex(ValueError, 'SCREENSHOT_LIMIT'):
            generate_batch(self.media, self.config, generate_candidate)

    def test_draft_preview_uses_cap_without_publishing(self):
        import uploader
        from utils.job_history import JobHistory
        from utils.upload_drafts import DraftStore
        category = uploader.categories()[0]['id']
        self.config.set('Paths', 'DATADIR', str(self.root))
        self.config.set('Paths', 'TEMPLATE_PATH', str(ROOT / 'files/template.txt'))
        self.config.set('Settings', 'SCREENSHOTS', 'true')
        self.config.set('Settings', 'SCREENSHOT_CATEGORIES', str(category))
        self.config.set('Settings', 'MEDIAINFO', 'false')
        self.config.set('MediaTools', 'SCREENSHOT_ENGINE', 'ffmpeg')
        self.config.set('MediaTools', 'SCREENSHOT_LIMIT', '5')
        config_path = self.root / 'preview.ini'
        with config_path.open('w', encoding='utf-8') as stream:
            self.config.write(stream)
        store = DraftStore(SimpleNamespace(history=JobHistory(self.root / 'history.db')))
        with patch.dict(os.environ, {'DIRTYBYTES_CONFIG': str(config_path), 'DIGITALCORE_CONFIG': str(config_path)}), patch.object(uploader, 'load_config', return_value=self.config), patch('utils.screenshot_utils.subprocess.run', side_effect=self.run_tool), patch('requests.sessions.Session.request', side_effect=AssertionError('Preview must not publish')):
            draft = store.save({'source': str(self.media), 'category': category})
            store.preview(draft['id'])
            store.preview_thread.join(15)
        self.assertFalse(store.preview_thread.is_alive())
        row = store.get(draft['id'])
        self.assertEqual(row['state'], 'ready', row['error'])
        self.assertEqual(len(row['preview']['images']), 5)
        self.assertEqual(len(self.frames), 5)
