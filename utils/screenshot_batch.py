"""Select one representative video or generate isolated previews for every video."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

from utils.mediainfo_utils import iter_media_files, media_priority, is_sample_path


def generate_batch(directory, config, generate_candidate):
    directory = Path(directory)
    mode = config.get('MediaTools', 'SCREENSHOT_VIDEO_MODE', fallback='single').strip().lower()
    if mode not in ('single', 'all'):
        raise ValueError('Choose single or all for MediaTools.SCREENSHOT_VIDEO_MODE.')
    files = sorted(iter_media_files(directory), key=media_priority)
    main = [path for path in files if not is_sample_path(path)]
    samples = [path for path in files if is_sample_path(path)]
    fallback = config.getboolean('Settings', 'SCREENSHOT_SAMPLE_FALLBACK', fallback=True)
    candidates = (main or (samples if fallback else [])) if mode == 'all' else main + (samples if fallback else [])
    if not candidates:
        print('No eligible video found; screenshots skipped.', flush=True)
        return
    target = Path(config.get('Paths', 'TMP_DIR')) / str(os.getpid()) / 'screens'
    target.mkdir(parents=True, exist_ok=True)
    for image in target.glob('*.jpg'):
        image.unlink()
    failures = []
    completed = 0
    for index, source in enumerate(candidates, 1):
        print(f'Video {index}/{len(candidates)}: {source.relative_to(directory)}', flush=True)
        try:
            # A failed video or MTN retry must never erase another video's previews.
            with tempfile.TemporaryDirectory(prefix='screens-video-', dir=target.parent) as scratch:
                scratch = Path(scratch)
                generate_candidate(source, scratch, config)
                if mode == 'all':
                    relative = source.relative_to(directory).as_posix()
                    digest = hashlib.sha256(relative.encode('utf-8')).hexdigest()[:10]
                    label = re.sub(r'[^A-Za-z0-9._-]+', '-', source.stem)[:48].strip('.-') or 'video'
                    prefix = f'{index:04d}-{label}-{digest}-'
                else:
                    prefix = ''
                for image in sorted(scratch.glob('*.jpg')):
                    # Short, unique names also distinguish identical stems in subfolders.
                    suffix = re.sub(r'[^A-Za-z0-9._-]+', '-', image.name)[-100:]
                    name = prefix + suffix if prefix else image.name
                    image.replace(target / name)
            completed += 1
            if mode == 'single':
                return
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
            failures.append(source.relative_to(directory).as_posix())
            print('Screenshot generation failed for ' + source.name + '.', flush=True)
    if failures and (not completed or config.getboolean('Settings', 'REQUIRE_SCREENSHOTS', fallback=True)):
        raise RuntimeError('Screenshots failed for: ' + ', '.join(failures))
    if failures:
        print('Continuing with partial previews because REQUIRE_SCREENSHOTS is disabled: ' + ', '.join(failures), flush=True)
