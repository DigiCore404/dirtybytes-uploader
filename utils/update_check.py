"""Public release notifications and installation-specific update instructions."""
import datetime
import os
from pathlib import Path
import re
import threading
import time
import requests
from utils.app_version import VERSION, NAME, REPOSITORY, SLUG, CONTAINER_ENV


def version_parts(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    if not match:
        raise ValueError('Not a stable release version.')
    return tuple(map(int, match.groups()))


def latest_release():
    response = requests.get('https://api.github.com/repos/' + REPOSITORY + '/releases/latest',
                            timeout=5, allow_redirects=False)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ValueError('Release information is unavailable.')
    row = response.json()
    if not isinstance(row, dict) or row.get('draft') or row.get('prerelease'):
        raise ValueError('Not a published stable release.')
    tag = str(row.get('tag_name', ''))
    version_parts(tag)
    version = tag.removeprefix('v')
    return {'latest_version': version,
            'release_url': 'https://github.com/' + REPOSITORY + '/releases/tag/' + tag,
            'notes': str(row.get('body') or '')[:12000]}


def instructions(version):
    version_parts(version)
    release = 'https://github.com/' + REPOSITORY + '/releases/tag/v' + version
    download = 'https://github.com/' + REPOSITORY + '/releases/download/v' + version + '/'
    stem = SLUG + '-seedbox-' + version
    # Commands are built only from our fixed repository and a validated version.
    native = ('(\nset -eu\nstage="$(mktemp -d)"\n'
              'curl -fL --retry 2 "' + download + stem + '.tar.gz" -o "$stage/' + stem + '.tar.gz"\n'
              'curl -fL --retry 2 "' + download + stem + '.sha256" -o "$stage/' + stem + '.sha256"\n'
              '(cd "$stage" && sha256sum --check --ignore-missing "' + stem + '.sha256")\n'
              'tar -xzf "$stage/' + stem + '.tar.gz" -C "$stage"\n'
              'rsync -rlt --exclude=config.ini --exclude=files/template.txt --exclude=files/filters.json "$stage/' + SLUG + '-seedbox/" ./\n'
              'bash install.sh\n)')
    return {'image': 'ghcr.io/' + REPOSITORY.lower() + ':latest',
            'docker_commands': 'docker compose pull uploader\ndocker compose up -d --no-deps uploader',
            'git_commands': 'git fetch --tags origin\ngit switch --detach v' + version + '\nbash install.sh',
            'package_commands': native,
            'release_url': release,
            'package_url': download + stem + '.tar.gz',
            'checksums_url': download + stem + '.sha256'}


class ReleaseChecker:
    def __init__(self):
        self.lock = threading.Lock()
        self.next_check = 0
        self.last_started = None
        self.data = {'status': 'not_checked', 'current_version': VERSION, 'latest_version': None,
                     'available': False, 'checked_at': None, 'notes': '',
                     'release_url': 'https://github.com/' + REPOSITORY + '/releases'}

    def status(self, enabled=True, force=False):
        with self.lock:
            if not enabled:
                result = dict(self.data, status='disabled', available=False)
            else:
                now = time.monotonic()
                due = now >= self.next_check or (force and (self.last_started is None or now - self.last_started >= 60))
                if self.data['status'] != 'checking' and due:
                    self.data['status'] = 'checking'
                    self.last_started = now
                    threading.Thread(target=self._check, daemon=True).start()
                result = dict(self.data)
        result['source_type'] = 'git' if (Path(__file__).resolve().parents[1] / '.git').exists() else 'package'
        result['installation'] = 'docker' if os.environ.get(CONTAINER_ENV) == '1' else 'native'
        result['instructions'] = instructions(result['latest_version'] or VERSION)
        return result

    def _check(self):
        try:
            release = latest_release()
            changes = dict(release or {})
            changes['available'] = bool(release and version_parts(release['latest_version']) > version_parts(VERSION))
            changes['status'] = 'available' if changes['available'] else 'current' if release else 'no_release'
            delay = 6 * 60 * 60
        except (requests.RequestException, ValueError, TypeError, KeyError):
            changes = {'status': 'unavailable'}
            delay = 30 * 60
        with self.lock:
            self.data.update(changes)
            self.data['checked_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.next_check = time.monotonic() + delay


def check(version):
    """Keep the existing optional CLI notification working."""
    try:
        release = latest_release()
        if release and version_parts(release['latest_version']) > version_parts(version):
            print('New ' + NAME + ' release: v' + release['latest_version'] + ' (' + release['release_url'] + ')', flush=True)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
