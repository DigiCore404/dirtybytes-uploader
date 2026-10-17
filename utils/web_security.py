"""Workspace credentials and direct-peer IP access control, persisted privately in SQLite."""
import hashlib
import hmac
import ipaddress
import json
import secrets
import configparser
import os
import sqlite3
import tempfile
from pathlib import Path
from contextlib import closing


def reset_password(database_path, password):
    """Local recovery changes only the workspace password, preserving other state."""
    if not 12 <= len(password) <= 256:
        raise ValueError('Use a password between 12 and 256 characters.')
    path = Path(database_path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS workspace_security (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL, allowed_ips TEXT NOT NULL)')
        row = db.execute('SELECT username FROM workspace_security WHERE id=1').fetchone()
        if row:
            db.execute('UPDATE workspace_security SET password_hash=? WHERE id=1', (password_hash(password),))
            return row[0]
        db.execute('INSERT INTO workspace_security VALUES (1,?,?,?)', ('admin', password_hash(password), '[]'))
        return 'admin'


def reset_password_interactive(database_path):
    import getpass
    password = getpass.getpass('New workspace password (12–256 characters): ')
    if password != getpass.getpass('Repeat password: '):
        raise ValueError('Passwords do not match. Nothing changed.')
    username = reset_password(database_path, password)
    print(f'Workspace password saved. Username: {username}. Restart the web service before signing in.')


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return 'pbkdf2_sha256$600000$' + salt + '$' + digest


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(rounds) != 600000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def networks(value):
    entries = value if isinstance(value, list) else str(value).replace(',', '\n').splitlines()
    if len(entries) > 100:
        raise ValueError('Use at most 100 IP addresses or CIDR ranges.')
    try:
        return list(dict.fromkeys(str(ipaddress.ip_network(str(v).strip(), strict=False)) for v in entries if str(v).strip()))
    except ValueError as exc:
        raise ValueError('Enter one valid IP address or CIDR network per line.') from exc


def allows(address, rules):
    try:
        ip = ipaddress.ip_address(address)
        if getattr(ip, 'ipv4_mapped', None):
            ip = ip.ipv4_mapped
        return not rules or any(ip in ipaddress.ip_network(rule) for rule in rules)
    except ValueError:
        return False


class Security:
    def consume_ini_login(self, config_path):
        """A nonempty INI password is a one-time local login override."""
        path = Path(config_path)
        config = configparser.ConfigParser(interpolation=None)
        config.read(path, encoding='utf-8')
        password = config.get('Web', 'PASSWORD', fallback='')
        if not password:
            return False
        username = config.get('Web', 'USERNAME', fallback=self.state()['username']).strip()
        if not 1 <= len(username) <= 100 or any(c in username for c in '\r\n\x00'):
            raise ValueError('Web.USERNAME must contain between 1 and 100 characters.')
        if not 12 <= len(password) <= 256:
            raise ValueError('Web.PASSWORD must contain between 12 and 256 characters.')
        config.set('Web', 'PASSWORD', '')
        # Prepare a private replacement before changing the saved login.
        fd, temporary = tempfile.mkstemp(prefix='.workspace-login-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                config.write(stream)
                stream.flush()
                os.fsync(stream.fileno())
            with self.history.connect() as db:
                db.execute('UPDATE workspace_security SET username=?,password_hash=? WHERE id=1',
                           (username, password_hash(password)))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True

    def __init__(self, history, password, username='admin', allowed_ips=''):
        self.history = history
        self.created = False
        with history.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS workspace_security (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL, allowed_ips TEXT NOT NULL)')
            if not db.execute('SELECT 1 FROM workspace_security WHERE id=1').fetchone():
                db.execute('INSERT INTO workspace_security VALUES (1,?,?,?)',
                           (username.strip() or 'admin', password_hash(password), json.dumps(networks(allowed_ips))))
                self.created = True

    def _row(self):
        with self.history.connect() as db:
            return dict(db.execute('SELECT * FROM workspace_security WHERE id=1').fetchone())

    def state(self):
        row = self._row()
        return {'username': row['username'], 'allowed_ips': json.loads(row['allowed_ips'])}

    def allowed(self, address):
        return allows(address, self.state()['allowed_ips'])

    def verify(self, username, password):
        row = self._row()
        valid_password = verify_password(str(password), row['password_hash'])
        return hmac.compare_digest(str(username).encode(), row['username'].encode()) and valid_password

    def update(self, data, address):
        row = self._row()
        if not verify_password(str(data.get('current_password', '')), row['password_hash']):
            raise ValueError('Enter your current workspace password to change access settings.')
        username = str(data.get('username', '')).strip()
        if not 1 <= len(username) <= 100 or any(c in username for c in '\r\n\x00'):
            raise ValueError('Enter a username between 1 and 100 characters.')
        password = str(data.get('password', ''))
        if password and not 12 <= len(password) <= 256:
            raise ValueError('Use a new password between 12 and 256 characters.')
        rules = networks(data.get('allowed_ips', []))
        if not allows(address, rules):
            raise ValueError('Keep your current IP address allowed to avoid locking yourself out.')
        encoded = password_hash(password) if password else row['password_hash']
        with self.history.connect() as db:
            db.execute('UPDATE workspace_security SET username=?,password_hash=?,allowed_ips=? WHERE id=1',
                       (username, encoded, json.dumps(rules)))
        return self.state()
