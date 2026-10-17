import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from utils.web_security import Security, reset_password, reset_password_interactive, verify_password
from utils.job_history import JobHistory
import configparser


class PasswordRecoveryTests(unittest.TestCase):
    def test_ini_override_consumed_once_and_other_settings_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            history = JobHistory(path / 'uploads.db')
            security = Security(history, 'original-password', 'old-owner', '127.0.0.1')
            ini = path / 'config.ini'
            ini.write_text('[Web]\nUSERNAME = new-owner\nPASSWORD = new-long-password\n[Other]\nVALUE = keep-me\n', encoding='utf-8')
            self.assertTrue(security.consume_ini_login(ini))
            self.assertTrue(security.verify('new-owner', 'new-long-password'))
            self.assertFalse(security.verify('old-owner', 'original-password'))
            self.assertEqual(security.state()['allowed_ips'], ['127.0.0.1/32'])
            config = configparser.ConfigParser(interpolation=None)
            config.read(ini, encoding='utf-8')
            self.assertEqual(config.get('Web', 'PASSWORD'), '')
            self.assertEqual(config.get('Other', 'VALUE'), 'keep-me')
            security.update({'username': 'new-owner', 'current_password': 'new-long-password',
                             'password': 'later-web-password', 'allowed_ips': ['127.0.0.1']}, '127.0.0.1')
            restarted = Security(history, 'different-bootstrap')
            self.assertFalse(restarted.consume_ini_login(ini))
            self.assertTrue(restarted.verify('new-owner', 'later-web-password'))

    def test_invalid_ini_override_preserves_login_and_ini(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            security = Security(JobHistory(path / 'uploads.db'), 'original-password')
            ini = path / 'config.ini'
            original = '[Web]\nUSERNAME = admin\nPASSWORD = short\n'
            ini.write_text(original, encoding='utf-8')
            with self.assertRaises(ValueError):
                security.consume_ini_login(ini)
            self.assertEqual(ini.read_text(encoding='utf-8'), original)
            self.assertTrue(security.verify('admin', 'original-password'))

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
