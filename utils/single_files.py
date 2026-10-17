"""Prepare a loose file as a release directory without moving or copying data."""
import os
from pathlib import Path


def prepare(value, config):
    root = Path(config.get('Paths', 'DATADIR')).resolve(strict=True)
    source = Path(value).expanduser()
    source = (source if source.is_absolute() else root / source).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('Choose a file inside the content library.')
    if not source.stat().st_size or source.stem in ('', '.', '..'):
        raise ValueError('Choose a nonempty file with a release name.')
    mode = config.get('SingleFiles', 'LINK_MODE', fallback='hardlink')
    if mode not in ('hardlink', 'softlink'):
        raise ValueError('Choose Hardlink or Softlink in Settings → Single-file uploads.')
    folder = source.parent / source.stem
    target = folder / source.name
    if folder.is_symlink():
        raise ValueError('The release folder already exists as a link. Choose another file or folder.')
    if folder.exists():
        if folder.is_dir() and set(folder.iterdir()) == {target} and target.exists() and target.samefile(source):
            return {'source': str(folder), 'original_file': str(source),
                    'link_mode': 'softlink' if target.is_symlink() else 'hardlink', 'created': False}
        raise ValueError('A different release folder already exists with this name. Nothing was overwritten.')
    try:
        folder.mkdir()
    except OSError as exc:
        raise ValueError('Cannot create the release folder beside this file. Allow write access to its parent folder; Docker media must be mounted read/write.') from exc
    try:
        if mode == 'hardlink':
            os.link(source, target)
        else:
            target.symlink_to(os.path.relpath(source, folder))
    except OSError as exc:
        folder.rmdir()
        raise ValueError('Could not create the '+mode+'. Hardlinks need the same filesystem; softlinks need symlink support. The original file was left unchanged.') from exc
    return {'source': str(folder), 'original_file': str(source), 'link_mode': mode, 'created': True}
