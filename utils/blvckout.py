"""Read-only BLVCKOUT V1 metadata. Keys never leave the fixed API origin."""
import re
from urllib.parse import urlsplit
import requests
from utils.metadata_text import plain_description, bounded_names

API = 'https://blvckout.foo/api/v1'


def request(token, path, params=None):
    if not token:
        raise ValueError('Add your BLVCKOUT API key in Settings first.')
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(API + path, params=params, headers={
                'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
                'User-Agent': 'Uploader-BLVCKOUT/1.0'}, timeout=20, allow_redirects=False)
            if response.status_code in (401, 403):
                raise ValueError('BLVCKOUT rejected this key. Check its expiry and read permissions in Settings.')
            if response.status_code == 429:
                raise ValueError('BLVCKOUT rate limit reached. Try again later.')
            if response.status_code != 200:
                raise ValueError('BLVCKOUT is unavailable. Try again later.')
            return response.json()
    except requests.RequestException as exc:
        raise ValueError('Could not read BLVCKOUT metadata. Try again later.') from exc


def normalize(row):
    def names(values):
        return ', '.join(str(v.get('name', '') if isinstance(v, dict) else v) for v in (values or []) if isinstance(v, (str, dict)))[:1000]
    images = []
    for value in [row.get('front_cover'), row.get('back_cover')]:
        if not isinstance(value, str) or any(c.isspace() or c in '[]' for c in value):
            continue
        try:
            p = urlsplit(value)
            if p.scheme == 'https' and p.hostname and not p.username and not p.password and value not in images:
                images.append(value)
        except ValueError:
            continue
    date = str(row.get('release_date') or '')[:10]
    year = str(row.get('production_year') or row.get('year') or date[:4] or '')
    runtime = str(row.get('runtime_minutes') or '')
    return {'id': str(row.get('id') or ''), 'kind': 'movies', 'provider': 'blvckout',
            'site': 'BLVCKOUT', 'title': str(row.get('title') or '')[:500], 'date': date,
            'description': plain_description(str(row.get('description') or row.get('notes') or '')[:30000]),
            'images': images, 'metadata': {'studio': str(row.get('studio') or '')[:1000],
            'performers': names(row.get('performers')), 'content_tags': bounded_names(names(row.get('genres'))),
            'release_year': year if re.fullmatch(r'(19|20)\d{2}', year) else '',
            'runtime_minutes': runtime if runtime.isdigit() and 1 <= int(runtime) <= 2000 else ''}}


def search(token, query, kind=None):
    if not 2 <= len(query.strip()) <= 250:
        raise ValueError('Enter a title or release name (2–250 characters).')
    data = request(token, '/releases', {'q': query.strip(), 'limit': 12})
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('BLVCKOUT returned an unexpected search result.')
    return [normalize(row) for row in data['items'][:12] if isinstance(row, dict)]


def detail(token, identity, kind=None):
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', identity):
        raise ValueError('Choose a valid BLVCKOUT result.')
    row = request(token, '/releases/' + identity)
    if not isinstance(row, dict) or not row.get('id'):
        raise ValueError('BLVCKOUT returned an unexpected result.')
    return normalize(row)
