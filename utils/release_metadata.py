"""Extract DirtyBytes upload metadata from a release name and its files.

Everything here is heuristic parsing of standard scene naming:

    Site.YY.MM.DD.Performer[.And.Performer2][.Scene.Title].XXX.<res>p.MP4-GRP
    SiteName.Performer.Title.XXX.1080p.MP4-GRP
    Movie.Title.XXX.DVDRip.x264-GRP
    Site.com_YY.MM.DD.Name.XXX.iMAGESET-GRP

Produced fields match the DirtyBytes upload API exactly:
    studio, performers, release_year, runtime_minutes, language
"""

import re
import subprocess
from pathlib import Path

MAX_STUDIO_LEN = 120
MAX_PERFORMERS = 100

DATE_RE = re.compile(r'(?:^|[._ -])(\d{2})[._ -](\d{2})[._ -](\d{2})(?:[._ -]|$)')
YEAR_RE = re.compile(r'(?:^|[._ -])((?:19|20)\d{2})(?:[._ -]|$)')
MARKER_RE = re.compile(r'(?i)[._ -]XXX(?:[._ -]|$)')

# Tokens that mean "this is not a performer name, the title has started"
TITLE_STOPWORDS = {
    'a', 'an', 'the', 'and', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
    'her', 'his', 'my', 'your', 'our', 'their', 'its', 'first', 'best',
    'behind', 'how', 'what', 'when', 'two', 'three',
}

LANGUAGE_TOKENS = {
    'french': 'French', 'german': 'German', 'spanish': 'Spanish',
    'italian': 'Italian', 'swedish': 'Swedish', 'dutch': 'Dutch',
    'flemish': 'Dutch', 'japanese': 'Japanese', 'russian': 'Russian',
    'czech': 'Czech', 'polish': 'Polish', 'portuguese': 'Portuguese',
    'brazilian': 'Portuguese', 'hungarian': 'Hungarian', 'danish': 'Danish',
    'norwegian': 'Norwegian', 'finnish': 'Finnish', 'korean': 'Korean',
    'chinese': 'Chinese', 'thai': 'Thai', 'hindi': 'Hindi', 'turkish': 'Turkish',
}

MEDIA_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.mpg', '.m2ts', '.vob', '.m4v'}


def _strip_group(name):
    """Remove the trailing -GROUP tag."""
    if '-' in name:
        head, _, tail = name.rpartition('-')
        if tail and '.' not in tail and ' ' not in tail:
            return head
    return name


def _tokens(name):
    return [t for t in re.split(r'[._ ]+', name) if t]


def _looks_like_site(token):
    """CamelCase-ish single token: ScandalousGFs, NikkyBlond, BrazzersExxtra."""
    return bool(re.search(r'[a-z][A-Z0-9]', token)) or token.lower().endswith(('gfs', 'milfs'))


def extract_studio(release_name):
    name = _strip_group(release_name)

    # Site.com_... style (imagesets): everything before the first underscore
    if '_' in name.split('.XXX')[0].split('.xxx')[0]:
        head = name.split('_', 1)[0]
        head = re.sub(r'(?i)\.(com|net|org|tv|xxx)$', '', head)
        studio = head.replace('.', ' ').strip()
        return studio[:MAX_STUDIO_LEN]

    date_match = DATE_RE.search(name)
    tokens = _tokens(name)
    if not tokens:
        return ''

    if date_match:
        # Everything before the date is the site/studio
        head = name[:date_match.start()].strip('._ -')
        studio = ' '.join(_tokens(head))
        return studio[:MAX_STUDIO_LEN]

    # Undated: first token only if it clearly looks like a site name
    if _looks_like_site(tokens[0]):
        return tokens[0][:MAX_STUDIO_LEN]
    return ''


def extract_performers(release_name):
    """Performer names from dated releases: Date.P1[.And.P2][.Title].XXX"""
    name = _strip_group(release_name)
    date_match = DATE_RE.search(name)
    marker = MARKER_RE.search(name)
    if not date_match:
        return ''  # undated: performer position is ambiguous, don't guess

    segment = name[date_match.end():marker.start() if marker else len(name)]
    tokens = _tokens(segment)
    performers = []

    i = 0
    while i < len(tokens) and len(performers) < MAX_PERFORMERS:
        if tokens[i].lower() in TITLE_STOPWORDS:
            break
        # Take up to two tokens as one name, stopping before 'And'
        words = [tokens[i]]
        if i + 1 < len(tokens) and tokens[i + 1].lower() not in TITLE_STOPWORDS | {'and'} :
            words.append(tokens[i + 1])
        performers.append(' '.join(words))
        i += len(words)
        # Another performer only follows an explicit 'And'
        if i < len(tokens) and tokens[i].lower() == 'and':
            i += 1
        else:
            break

    return ', '.join(performers)


def extract_release_year(release_name):
    name = _strip_group(release_name)
    date_match = DATE_RE.search(name)
    if date_match:
        return str(2000 + int(date_match.group(1)))
    year_match = YEAR_RE.search(name)
    if year_match:
        return year_match.group(1)
    return ''


def extract_language(release_name):
    for token in _tokens(_strip_group(release_name)):
        lang = LANGUAGE_TOKENS.get(token.lower())
        if lang:
            return lang
    return ''


def runtime_minutes(directory):
    """Runtime in whole minutes from the largest media file, via mediainfo."""
    try:
        media = [p for p in Path(directory).rglob('*')
                 if p.is_file() and p.suffix.lower() in MEDIA_EXTS
                 and 'sample' not in str(p).lower()]
        if not media:
            return ''
        biggest = max(media, key=lambda p: p.stat().st_size)
        result = subprocess.run(
            ['mediainfo', '--Inform=General;%Duration%', str(biggest)],
            capture_output=True, text=True, timeout=60,
        )
        minutes = round(float(result.stdout.strip()) / 60000)
        if 1 <= minutes <= 65535:
            return str(minutes)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return ''


def extract_metadata(release_name, directory=None):
    """All name-derived upload fields; runtime included when directory is given."""
    metadata = {
        'studio': extract_studio(release_name),
        'performers': extract_performers(release_name),
        'release_year': extract_release_year(release_name),
        'language': extract_language(release_name),
    }
    if directory is not None:
        metadata['runtime_minutes'] = runtime_minutes(directory)
    # Only send fields that actually have a value
    return {key: value for key, value in metadata.items() if value}