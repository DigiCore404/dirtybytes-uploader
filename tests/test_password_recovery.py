import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from utils.web_security import reset_password, reset_password_interactive, verify_password


class PasswordRecoveryTests(unittest.TestCase):
    def test_first_login_and_existing_state_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data/uploads.db'
            self.assertEqual(reset_password(path, 'first-long-password'), 'admin')
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE workspace_security SET username='owner', allowed_ips='[\"127.0.0.1\"]'")
                db.execute('CREATE TABLE history (message TEXT)')
                db.execute("INSERT INTO history VALUES ('keep this upload')")
            self.assertEqual(reset_password(path, 'second-long-password'), 'owner')
            with closing(sqlite3.connect(path)) as db, db:
                username, hashed, allowed = db.execute('SELECT username,password_hash,allowed_ips FROM workspace_security').fetchone()
                self.assertEqual(username, 'owner')
                self.assertEqual(allowed, '["127.0.0.1"]')
                self.assertTrue(verify_password('second-long-password', hashed))
                self.assertFalse(verify_password('first-long-password', hashed))
                self.assertEqual(db.execute('SELECT message FROM history').fetchone()[0], 'keep this upload')

    def test_invalid_or_mismatched_password_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data/uploads.db'
            with self.assertRaises(ValueError):
                reset_password(path, 'short')
            with patch('getpass.getpass', side_effect=['first-long-password', 'other-long-password']):
                with self.assertRaises(ValueError):
                    reset_password_interactive(path)
            self.assertFalse(path.exists())
