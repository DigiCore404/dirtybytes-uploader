"""Read tracker requests with the configured API key; filling happens on upload."""
import json
import re
from urllib.parse import urlsplit

import requests


def request_id(value=0):
    if value in (None, ''):
        return 0
    if isinstance(value, bool) or not re.fullmatch(r'\d{1,10}', str(value)) or not 0 <= int(value) <= 2147483647:
        raise ValueError('Use a positive numeric request ID, or 0 for a normal upload.')
    return int(value)


class TrackerRequests:
    def __init__(self, config):
        self.config = config
        self.base = config.get('Website', 'SITEURL').rstrip('/')
        parsed = urlsplit(self.base)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Configure a valid tracker site URL first.')
        self.key = config.get('Website', 'API_KEY', fallback='').strip()
        if not self.key:
            raise ValueError('Save your tracker API key in Settings first.')

    def get(self, path, params=None):
        headers = {'X-API-KEY': self.key, 'Accept': 'application/json',
                   'User-Agent': self.config.get('Network', 'UserAgent', fallback='Uploader/1.0')}
        try:
            with requests.get(self.base + '/api/v1/' + path, params=params, headers=headers,
                              timeout=self.config.getint('Network', 'Timeout', fallback=15),
                              verify=self.config.getboolean('Network', 'VERIFY_SSL', fallback=True),
                              allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403):
                    raise ValueError('The tracker denied access to requests. Check your API key and account permissions.')
                if response.status_code == 404:
                    raise ValueError('The request or tracker request API was not found.')
                if response.status_code != 200:
                    raise ValueError('Tracker requests returned HTTP ' + str(response.status_code) + '. Try again later.')
                chunks = []; size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise ValueError('The tracker request response is too large.')
                    chunks.append(chunk)
                raw = b''.join(chunks)
                data = json.loads(raw) if raw.strip() else []
                total = response.headers.get('X-Total-Count', '')
                return data, int(total) if total.isdigit() else None
        except (requests.RequestException, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError('Could not read tracker requests. Check the connection and try again.') from exc

    def normalize(self, row):
        if not isinstance(row, dict):
            raise ValueError('The tracker returned invalid request details.')
        identity = request_id(row.get('id'))
        if not identity:
            raise ValueError('The tracker returned a request without an ID.')
        return {'id': identity, 'title': str(row.get('request') or '')[:1000],
                'category': row.get('type'), 'added': str(row.get('added') or '')[:50],
                'reward': row.get('reward', 0), 'votes': row.get('votes', 0),
                'filled': str(row.get('filled', 0)) not in ('0', '', 'False', 'None'),
                'description': str(row.get('comment') or '')[:30000],
                'season': row.get('season', 0), 'imdb': str(row.get('imdbid2') or '')[:30],
                'url': self.base + '/requests/' + str(identity)}

    def listing(self, search='', category=0, offset=0, sort='added', order='desc'):
        if sort not in ('added', 'name', 'votes', 'reward') or order not in ('asc', 'desc'):
            raise ValueError('Choose a valid request sort order.')
        offset = max(0, min(int(offset), 1000000)); category = request_id(category)
        data, total = self.get('requests/search', {'search': str(search).strip()[:200], 'category': category,
                              'index': offset, 'limit': 25, 'sort': sort, 'order': order})
        if not isinstance(data, list):
            raise ValueError('The tracker returned an invalid request list.')
        rows = [self.normalize(row) for row in data]
        rows = [row for row in rows if not row['filled']]
        return {'requests': rows, 'total': total, 'offset': offset, 'limit': 25}

    def selected(self, identity):
        identity = request_id(identity)
        if not identity:
            return None
        data, _ = self.get('requests/' + str(identity))
        row = self.normalize(data.get('request') if isinstance(data, dict) else None)
        if row['id'] != identity:
            raise ValueError('The tracker returned a different request. Select it again.')
        if row['filled']:
            raise ValueError('This request has already been filled. Choose another request or clear the selection.')
        return row
