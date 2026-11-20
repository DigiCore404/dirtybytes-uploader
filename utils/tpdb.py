"""Read-only ThePornDB metadata; token is sent only to the fixed API origin."""
from utils.metadata_text import plain_description, bounded_names
import re
import math
from urllib.parse import urlsplit
import requests

API = 'https://api.theporndb.net'

def request(token, path, params=None):
    if not token:
        raise ValueError('Add your ThePornDB API token in Settings first.')
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(API + path, params=params, headers={
                'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
                'User-Agent': 'DirtyBytes-Uploader/2.2'}, timeout=20, allow_redirects=False)
            if response.status_code in (401, 403):
                raise ValueError('ThePornDB rejected this token. Check it in Settings.')
            if response.status_code == 429:
                raise ValueError('ThePornDB rate limit reached. Try again later.')
            if response.status_code != 200:
                raise ValueError('ThePornDB is unavailable. Try again later.')
            return response.json()['data']
    except (requests.RequestException, KeyError, TypeError) as exc:
        raise ValueError('Could not read ThePornDB metadata. Try again later.') from exc

def runtime_minutes(row):
    """TPDB duration is seconds; the tracker accepts whole minutes."""
    explicit = row.get('runtime_minutes')
    raw = explicit if explicit is not None else row.get('duration')
    if raw is None or isinstance(raw, bool):
        return ''
    try:
        if isinstance(raw, str) and ':' in raw and explicit is None:
            parts = raw.strip().split(':')
            if len(parts) not in (2, 3) or any(not p.isdigit() for p in parts):return ''
            if any(int(p) >= 60 for p in parts[1:]):return ''
            seconds = sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
        else:
            seconds = float(raw) * (60 if explicit is not None else 1)
        if not math.isfinite(seconds) or not 0 < seconds <= 120000:return ''
        return str(max(1, math.floor(seconds / 60 + 0.5)))
    except (TypeError, ValueError, OverflowError):
        return ''


def performer_names(values):
    names = []
    seen = set()
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict):continue
        parent = value.get('parent')
        name = parent.get('name') if isinstance(parent, dict) else None
        if not isinstance(name, str) or not name.strip():name = value.get('name')
        if not isinstance(name, str):continue
        name = name.strip()
        if name and name.casefold() not in seen:
            names.append(name);seen.add(name.casefold())
    return ', '.join(names)[:1000]


def normalize(row, kind):
    def names(values):
        return ', '.join(str(v.get('name', '')) for v in (values or []) if isinstance(v, dict) and v.get('name'))[:1000]
    site = row.get('site') or {}
    date = str(row.get('date') or '')
    # TPDB's poster is a signed thumbnail/transformation URL. Prefer the
    # supplied CDN image, preserving its path and query exactly as returned.
    background = row.get('background')
    candidates = ([background.get(size) for size in ('large', 'full', 'medium', 'small')]
                  if isinstance(background, dict) else [background])
    candidates.extend([row.get('image'), row.get('poster')])
    images = []
    for image in candidates:
        if not isinstance(image, str) or any(c.isspace() or c in '[]' for c in image):
            continue
        try:
            parsed = urlsplit(image)
            valid = parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
        except ValueError:
            valid = False
        if valid:
            images = [image]
            break
    return {'id': str(row.get('_id') or row.get('id') or ''), 'kind': kind,
            'title': str(row.get('title') or '')[:500], 'date': date[:10],
            'description': plain_description(str(row.get('description') or '')[:30000]), 'images': images,
            'metadata': {'studio': str(site.get('name') or '')[:1000],
                         'performers': performer_names(row.get('performers')), 'content_tags': bounded_names(names(row.get('tags'))),
                         'runtime_minutes': runtime_minutes(row),
                         'release_year': date[:4] if re.match(r'^(19|20)\d\d', date) else ''}}

def search(token, query, kind='scenes'):
    if kind not in ('scenes', 'movies') or not 2 <= len(query.strip()) <= 250:
        raise ValueError('Enter a title or release name (2–250 characters).')
    rows = request(token, '/' + kind, {'parse': query.strip(), 'limit': 12})
    if not isinstance(rows, list):
        raise ValueError('ThePornDB returned an unexpected search result.')
    return [normalize(row, kind) for row in rows[:12] if isinstance(row, dict)]

def detail(token, identity, kind):
    if kind not in ('scenes', 'movies') or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', identity):
        raise ValueError('Choose a valid ThePornDB result.')
    row = request(token, '/' + kind + '/' + identity)
    if not isinstance(row, dict):
        raise ValueError('ThePornDB returned an unexpected result.')
    return normalize(row, kind)
