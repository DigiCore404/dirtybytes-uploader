"""Saved media folders and category previews using the upload filter rules."""
import configparser
import json
import os
from pathlib import Path
import re
import tempfile
from utils.app_version import SLUG


def load_rules(config):
    return json.loads(Path(config.get('Paths', 'FILTERS')).read_text(encoding='utf-8'))


def match_category(name, rules, categories):
    """Keep the same first-match order as the CLI filters.json engine."""
    valid = {int(row['id']): row['name'] for row in categories}
    def matches(patterns):
        return any(re.search(p, name, re.I) for p in patterns or [])
    for group in rules.values():
        patterns = group.get('patterns', {})
        if matches(patterns.get('exclude_patterns')) or not matches(patterns.get('initial')):
            continue
        for rule in group.get('categories', []):
            if matches(rule.get('exclude_patterns')):
                continue
            if matches(rule.get('patterns')) or SLUG == 'digitalcore-uploader' and not rule.get('patterns'):
                identity = int(rule['cat_id'])
                if identity in valid:
                    return {'id': identity, 'name': valid[identity]}
    for group in rules.values():
        for rule in group.get('categories', []):
            if rule.get('default') and int(rule['cat_id']) in valid:
                identity = int(rule['cat_id'])
                return {'id': identity, 'name': valid[identity]}
    return None


def validate_rules(text, categories):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 500000:
        raise ValueError('filters.json must be JSON text smaller than 500 KB.')
    try:
        rules = json.loads(text)
    except ValueError as exc:
        raise ValueError('Invalid JSON: ' + str(exc)) from exc
    if not isinstance(rules, dict) or not rules:
        raise ValueError('Use a JSON object containing filter groups.')
    valid = {int(row['id']): row['name'] for row in categories}
    def patterns(value):
        if not isinstance(value, list) or len(value) > 2000:
            raise ValueError('Each pattern list must contain regular-expression strings.')
        for pattern in value:
            if not isinstance(pattern, str) or len(pattern) > 16000:
                raise ValueError('Patterns must be strings of at most 16000 characters.')
            try:
                re.compile(pattern, re.I)
            except re.error as exc:
                raise ValueError('Invalid regex: ' + str(exc)) from exc
    for group in rules.values():
        if not isinstance(group, dict) or not isinstance(group.get('patterns'), dict) or not isinstance(group.get('categories'), list):
            raise ValueError('Each group needs patterns and a categories list.')
        for field in ('initial', 'exclude_patterns'):
            patterns(group['patterns'].get(field, []))
        for rule in group['categories']:
            if not isinstance(rule, dict) or isinstance(rule.get('cat_id'), bool) or not str(rule.get('cat_id', '')).isdigit() or int(rule['cat_id']) not in valid:
                raise ValueError('Each category must use a valid site category ID in cat_id.')
            if not isinstance(rule.get('name'), str) or not rule['name'].strip():
                rule['name'] = valid[int(rule['cat_id'])]
            if 'default' in rule and not isinstance(rule['default'], bool):
                raise ValueError('The default flag must be true or false.')
            for field in ('patterns', 'exclude_patterns'):
                patterns(rule.get(field, []))
    return rules


def save_rules(text, config_path, categories):
    rules = validate_rules(text, categories)
    config_path = Path(config_path)
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path, encoding='utf-8')
    if not config.has_section('Paths'):
        config.add_section('Paths')
    # The image's /app/files is not writable by the application user. Keep edits
    # beside config.ini in its existing persistent configuration volume.
    target = config_path.parent / 'filters.json'
    config.set('Paths', 'FILTERS', str(target))
    def atomic(path, content):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temp = Path(output.name)
            try:
                if os.name != 'nt':
                    temp.chmod(0o600)
                output.write(content)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
        temp.replace(path)
    from io import StringIO
    output = StringIO()
    config.write(output)
    atomic(target, json.dumps(rules, indent=2, ensure_ascii=False) + '\n')
    atomic(config_path, output.getvalue())
    return rules


class Library:
    def __init__(self, history):
        self.history = history
        with history.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS library_folders (path TEXT PRIMARY KEY)')

    def folders(self):
        with self.history.connect() as db:
            return [row['path'] for row in db.execute('SELECT path FROM library_folders ORDER BY path')]

    def add(self, path):
        with self.history.connect() as db:
            db.execute('INSERT OR IGNORE INTO library_folders(path) VALUES (?)', (str(path),))

    def remove(self, path):
        with self.history.connect() as db:
            db.execute('DELETE FROM library_folders WHERE path=?', (str(path),))
