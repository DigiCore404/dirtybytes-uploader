"""Select one representative video or generate isolated previews for every video."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from utils.mediainfo_utils import iter_media_files, media_priority, is_sample_path


def generate_batch(directory, config, generate_candidate, category_id=None):
    limit = config.getint('MediaTools', 'SCREENSHOT_LIMIT', fallback=0)
    if not 0 <= limit <= 10000:
        raise ValueError('MediaTools.SCREENSHOT_LIMIT must be between 0 and 10000 (0 = unlimited).')
    directory = Path(directory)
    mode = config.get('MediaTools', 'SCREENSHOT_VIDEO_MODE', fallback='auto').strip().lower()
    if mode not in ('auto', 'single', 'all'):
        raise ValueError('Choose auto, single or all for MediaTools.SCREENSHOT_VIDEO_MODE.')
    if mode == 'auto':
        categories = json.loads((Path(__file__).resolve().parents[1] / 'files/dirtybytes-categories.json').read_text(encoding='utf-8'))
        pack = any(str(row['id']) == str(category_id) and 'PACKS' in row['name'].upper().split('/') for row in categories)
        mode = 'all' if pack else 'single'
        print('Automatic video selection: ' + ('all videos (pack).' if pack else 'one video (single release).'), flush=True)
    files = sorted(iter_media_files(directory), key=media_priority)
    main = [path for path in files if not is_sample_path(path)]
    samples = [path for path in files if is_sample_path(path)]
    fallback = config.getboolean('Settings', 'SCREENSHOT_SAMPLE_FALLBACK', fallback=True)
    candidates = (main or (samples if fallback else [])) if mode == 'all' else main + (samples if fallback else [])
    if not candidates:
        if config.getboolean('Settings','REQUIRE_SCREENSHOTS',fallback=True):
            raise RuntimeError('Screenshots are required, but no eligible video was found. Check the selected source and screenshot categories.')
        print('No eligible video found; screenshots skipped because REQUIRE_SCREENSHOTS is disabled.', flush=True)
        return
    target = Path(config.get('Paths', 'TMP_DIR')) / str(os.getpid()) / 'screens'
    target.mkdir(parents=True, exist_ok=True)
    for image in target.glob('*.jpg'):
        image.unlink()
    failures = []
    completed = 0
    produced = 0
    for index, source in enumerate(candidates, 1):
        print(f'Video {index}/{len(candidates)}: {(Path(source.name) if directory.is_file() else source.relative_to(directory))}', flush=True)
        try:
            # A failed video or MTN retry must never erase another video's previews.
            with tempfile.TemporaryDirectory(prefix='screens-video-', dir=target.parent) as scratch:
                scratch = Path(scratch)
                candidate_config = config
                if limit:
                    remaining = limit - produced
                    candidate_config = copy.deepcopy(config)
                    engine = config.get('MediaTools', 'SCREENSHOT_ENGINE', fallback='ffmpeg').strip().lower()
                    sheet = engine == 'mtn' and config.getboolean('MediaTools', 'SCREENSHOT_SHEET', fallback=True)
                    singles = config.getint('MediaTools', 'SCREENSHOT_SINGLES', fallback=5)
                    singles = min(12, max(0 if engine == 'mtn' else 1, singles))
                    candidate_config.set('MediaTools', 'SCREENSHOT_SINGLES', str(min(singles, remaining - int(sheet))))
                generate_candidate(source, scratch, candidate_config)
                images = sorted(scratch.glob('*.jpg'))
                if limit:
                    # Keep a requested sheet first; it counts as one output image.
                    images.sort(key=lambda image: (not image.name.endswith('-sheet.jpg'), image.name))
                    images = images[:limit - produced]
                if mode == 'all':
                    relative = (Path(source.name) if directory.is_file() else source.relative_to(directory)).as_posix()
                    digest = hashlib.sha256(relative.encode('utf-8')).hexdigest()[:10]
                    label = re.sub(r'[^A-Za-z0-9._-]+', '-', source.stem)[:48].strip('.-') or 'video'
                    prefix = f'{index:04d}-{label}-{digest}-'
                else:
                    prefix = ''
                for image in images:
                    # Short, unique names also distinguish identical stems in subfolders.
                    suffix = re.sub(r'[^A-Za-z0-9._-]+', '-', image.name)[-100:]
                    name = prefix + suffix if prefix else image.name
                    image.replace(target / name)
            produced += len(images)
            completed += 1
            if limit and produced >= limit:
                print(f'Screenshot limit reached: {produced}/{limit}; remaining videos skipped.', flush=True)
            if mode == 'single':
                return
            if limit and produced >= limit:
                break
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
            failures.append((Path(source.name) if directory.is_file() else source.relative_to(directory)).as_posix())
            print('Screenshot generation failed for ' + source.name + '.', flush=True)
    if failures and (not completed or config.getboolean('Settings', 'REQUIRE_SCREENSHOTS', fallback=True)):
        raise RuntimeError('Screenshots failed for: ' + ', '.join(failures))
    if failures:
        print('Continuing with partial previews because REQUIRE_SCREENSHOTS is disabled: ' + ', '.join(failures), flush=True)
