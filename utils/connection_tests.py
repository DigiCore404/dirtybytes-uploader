"""Explicit connection checks using a temporary copy of uploader settings."""
import base64
import copy
import importlib
from urllib.parse import urlparse
import requests
from utils import image_host
from utils.app_version import NAME, SLUG
from utils.web_settings import apply

TEST_IMAGE = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNoaGgAAAMEAYFL09IQAAAAAElFTkSuQmCC')
FIELDS = {'api_key': ('Website', 'API_KEY'), 'image_host_key': ('ImageHost', 'API_KEY'),
          'tpdb_token': ('ThePornDB', 'TOKEN'), 'tmdb_token': ('TMDB', 'TOKEN'),
          'igdb_client_id': ('IGDB', 'CLIENT_ID'), 'igdb_client_secret': ('IGDB', 'CLIENT_SECRET')}


class CheckError(ValueError):
    pass


def check(saved, data):
    target = str(data.get('target', ''))
    supported = {'site', 'image_host'} | ({'tmdb', 'igdb', 'tvmaze'} if SLUG == 'digitalcore-uploader' else {'tpdb'})
    if target not in supported:
        raise ValueError('Choose a supported API to test.')
    config = copy.deepcopy(saved)
    for key, (section, option) in FIELDS.items():
        value = str(data.get(key, '')).strip()
        if not value:
            continue
        if len(value) > 8000 or any(c in value for c in '\r\n\x00'):
            raise ValueError('Credentials must be a single line.')
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
    if target == 'image_host':
        provider = str(data.get('image_host') or image_host.provider(config))
        own = 'digitalcore' if SLUG == 'digitalcore-uploader' else 'dirtybytes'
        if provider not in (own, 'imgbb', 'imghost'):
            raise ValueError('Choose a supported image host.')
        config.set('ImageHost', 'PROVIDER', provider)
        fields = data.get('config_fields', {})
        if not isinstance(fields, dict) or set(fields) - {'ImageHost'}:
            raise ValueError('Only image-host fields can be used in this test.')
        apply(config, fields)
    try:
        if target == 'site':
            key = config.get('Website', 'API_KEY', fallback='').strip()
            if not key:
                raise CheckError('Enter your site API key first.')
            endpoint = config.get('Website', 'SITEURL').rstrip('/')
            parsed = urlparse(endpoint)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise CheckError('The site URL must be a complete HTTP(S) URL.')
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(endpoint + '/api/v1/torrents', params={'limit': 1},
                    headers={'X-API-KEY': key, 'Accept': 'application/json', 'User-Agent': NAME},
                    timeout=15, allow_redirects=False)
                if response.status_code in (401, 403):
                    raise CheckError('The site rejected the API key or this account does not have API access.')
                if response.status_code == 429:
                    raise CheckError('The site rate limit was reached. Try again later.')
                if response.status_code != 200:
                    raise CheckError('The site returned HTTP ' + str(response.status_code) + '. Check its availability.')
                payload = response.json()
                if not isinstance(payload, (dict, list)) or isinstance(payload, dict) and payload.get('error'):
                    raise CheckError('The site did not return a successful API response.')
            message = 'Site API connected. The API key was accepted.'
        elif target == 'image_host':
            image_host.upload(config, 'uploader-connection-test.png', TEST_IMAGE)
            message = 'Image host works: a small test image was uploaded successfully.'
        elif target == 'tpdb':
            module = importlib.import_module('utils.tpdb')
            result = module.request(config.get('ThePornDB', 'TOKEN', fallback=''), '/scenes', {'limit': 1})
            if not isinstance(result, list):
                raise CheckError('ThePornDB returned an unexpected response.')
            message = 'ThePornDB connected. The token was accepted.'
        elif target == 'tmdb':
            module = importlib.import_module('utils.tmdb')
            result = module.request(config.get('TMDB', 'TOKEN', fallback=''), '/configuration')
            if not isinstance(result, dict) or 'images' not in result:
                raise CheckError('TMDB returned an unexpected response.')
            message = 'TMDB connected. The API key or read access token was accepted.'
        elif target == 'igdb':
            module = importlib.import_module('utils.igdb')
            module.request(config.get('IGDB', 'CLIENT_ID', fallback=''), config.get('IGDB', 'CLIENT_SECRET', fallback=''), 'fields id; limit 1;')
            message = 'IGDB connected. Twitch authentication and game API access both work.'
        else:
            module = importlib.import_module('utils.tvmaze')
            result = module.request('/shows/1')
            if not isinstance(result, dict) or not result.get('id'):
                raise CheckError('TVmaze returned an unexpected response.')
            message = 'TVmaze is reachable. No API key is needed.'
        return {'ok': True, 'message': message}
    except requests.exceptions.SSLError:
        return {'ok': False, 'message': 'TLS certificate validation failed. Check the server certificate and system clock.'}
    except requests.exceptions.Timeout:
        return {'ok': False, 'message': 'The connection timed out. Check network access and try again.'}
    except requests.RequestException:
        return {'ok': False, 'message': 'Could not connect to the API. Check DNS and network access.'}
    except CheckError as exc:
        return {'ok': False, 'message': str(exc)}
    except (ValueError, TypeError, KeyError) as exc:
        safe = {
            'Add your ThePornDB API token in Settings first.',
            'ThePornDB rejected this token. Check it in Settings.',
            'Add your TMDB API read access token in Settings first.',
            'TMDB rejected the token. Check Settings.',
            'Add your IGDB / Twitch Client ID and Client secret in Settings first.',
            'Twitch rejected the IGDB application credentials. Check Settings.',
            'Add your ImgBB API key in Settings first.',
            'Add your imghost.dev API key in Settings first.',
            'Image host rejected the API key or upload permissions. Check Settings.'}
        if str(exc) in safe:
            return {'ok': False, 'message': str(exc)}
        # Never return upstream bodies, URLs or exceptions: they can contain keys.
        return {'ok': False, 'message': 'The API test failed. Check the credentials, selected host and network access.'}
