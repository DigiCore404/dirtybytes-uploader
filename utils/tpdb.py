"""Read-only ThePornDB metadata; token is sent only to the fixed API origin."""
import re
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

def normalize(row, kind):
    def names(values):
        return ', '.join(str(v.get('name', '')) for v in (values or []) if isinstance(v, dict) and v.get('name'))[:1000]
    site = row.get('site') or {}
    date = str(row.get('date') or '')
    image = row.get('poster')
    if not isinstance(image, str):
        image = (row.get('background') or {}).get('large') if isinstance(row.get('background'), dict) else ''
    images = [image] if image and image.startswith('https://') and not any(c in image for c in '[]\r\n') else []
    return {'id': str(row.get('_id') or row.get('id') or ''), 'kind': kind,
            'title': str(row.get('title') or '')[:500], 'date': date[:10],
            'description': str(row.get('description') or '')[:30000], 'images': images,
            'metadata': {'studio': str(site.get('name') or '')[:1000],
                         'performers': names(row.get('performers')), 'content_tags': names(row.get('tags')),
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
