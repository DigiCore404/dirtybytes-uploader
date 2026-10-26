"""Non-destructive, case-insensitive torrent payload exclusions."""
import fnmatch
import re
from pathlib import Path


def patterns(config):
    raw = config.get('Torrent', 'EXCLUDE_PATTERNS', fallback='')
    values = list(dict.fromkeys(p.strip().replace('\\', '/') for p in re.split(r'[,;\n]+', raw) if p.strip()))
    if len(values) > 100 or any(len(p) > 250 or '\x00' in p or '\r' in p or p.startswith('/') or '..' in p.split('/') for p in values):
        raise ValueError('Use up to 100 relative exclusion patterns, such as *.nfo, *.txt or Sample/*.jpg.')
    return values


def matches(relative, globs):
    relative = str(relative).replace('\\', '/').casefold()
    return any(fnmatch.fnmatchcase(relative if '/' in p else relative.rsplit('/', 1)[-1], p.casefold()) for p in globs)


def check_source(source, globs):
    if not globs:
        return
    source = Path(source)
    files = [source] if source.is_file() else [p for p in source.rglob('*') if p.is_file()]
    if files and all(matches(p.name if source.is_file() else p.relative_to(source).as_posix(), globs) for p in files):
        raise ValueError('Torrent exclusions remove every file in this release. Nothing was hashed or deleted.')
