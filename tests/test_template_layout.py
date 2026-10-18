import tempfile
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.template_utils import prepare_template

class TemplateLayoutTests(unittest.TestCase):
    def test_default_description_is_centered_and_empty_sections_collapse(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            output = Path(folder) / 'description.txt'
            prepare_template(ROOT / 'files/template.txt', output, {'!releasename!': 'Release',
                '!description!': '', '!imageupload!': '', '!screenshots!': '', '!nfo!': '', '!version!': 'test'})
            text = output.read_text(encoding='utf-8')
            self.assertIn('[c][b]Release[/b][/c]', text)
            self.assertNotIn('\n\n\n', text)
            self.assertNotIn('[c][/c]', text)
            self.assertTrue(text.endswith('[/url][/c]'))

    def test_nfo_and_image_alignment_survive_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            output = Path(folder) / 'description.txt'
            nfo = '[code]A\n\n\n   B[/code]'
            image = '[c][img]https://example.invalid/a.jpg[/img][/c]'
            prepare_template(ROOT / 'files/template.txt', output, {'!releasename!': 'Release',
                '!description!': 'Summary', '!imageupload!': image, '!screenshots!': '', '!nfo!': nfo, '!version!': 'test'})
            text = output.read_text(encoding='utf-8')
            self.assertIn(nfo, text)
            self.assertIn('[c]Summary[/c]', text)
            self.assertIn(image, text)
            self.assertNotIn('[c][c]', text)
