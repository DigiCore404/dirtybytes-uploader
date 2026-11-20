import configparser
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils.artwork import contact_sheet_artwork

class ContactSheetArtworkTests(unittest.TestCase):
    def config(self, mode):
        c=configparser.ConfigParser();c['MediaTools']={'CONTACT_SHEET_ARTWORK':mode};return c

    def test_default_does_not_override_selected_artwork(self):
        self.assertEqual(contact_sheet_artwork(self.config('none'),{'mtn-sheet.jpg':'https://image.test/sheet.jpg'},['mtn-sheet.jpg']),{})

    def test_backdrop_keeps_cover_and_uses_a_sheet_rather_than_first_frame(self):
        result=contact_sheet_artwork(self.config('backdrop'),{'frame.jpg':'https://image.test/frame.jpg','mtn-sheet.jpg':'https://image.test/sheet.jpg'},['frame.jpg','mtn-sheet.jpg'])
        self.assertEqual(result,{'backdrop_url':'https://image.test/sheet.jpg'})

    def test_pack_choice_is_deterministic_and_skips_failed_sheets(self):
        self.assertEqual(contact_sheet_artwork(self.config('both'),{'0002-sheet.jpg':'https://image.test/two.jpg'},['0002-sheet.jpg','0001-sheet.jpg']),{'firstpic':'https://image.test/two.jpg','backdrop_url':'https://image.test/two.jpg'})

    def test_missing_sheet_preserves_existing_artwork(self):
        self.assertEqual(contact_sheet_artwork(self.config('backdrop'),{'frame.jpg':'https://image.test/frame.jpg'},['frame.jpg']),{})

    def test_failed_sheet_upload_stops_requested_artwork(self):
        with self.assertRaisesRegex(RuntimeError,'Publication stopped'):
            contact_sheet_artwork(self.config('backdrop'),{'frame.jpg':'https://image.test/frame.jpg'},['mtn-sheet.jpg','frame.jpg'])

    def test_bad_mode_is_rejected(self):
        with self.assertRaises(ValueError):contact_sheet_artwork(self.config('invalid'),{},[])
