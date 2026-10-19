"""Prepare an imported torrent for mkbrr modify without reading/hashing media."""
from pathlib import Path
from utils.torrent_metadata import TorrentMetadata, decode

def encode(value):
    if isinstance(value,bytes):return str(len(value)).encode()+b':'+value
    if type(value) is int:return b'i'+str(value).encode()+b'e'
    if isinstance(value,list):return b'l'+b''.join(encode(x) for x in value)+b'e'
    if isinstance(value,dict):return b'd'+b''.join(encode(k)+encode(v) for k,v in sorted(value.items()))+b'e'
    raise ValueError('Unsupported torrent metadata.')

def validate(original, source, allowed_root=None):
    """Check paths and sizes only; never read media bytes or start a hasher."""
    metadata = original if isinstance(original, TorrentMetadata) else TorrentMetadata.read(original)
    source = Path(source).resolve(strict=True)
    meta, _ = decode(metadata.raw)
    if source.is_file() and (b'files' in meta[b'info'] or source.name != metadata.name):
        raise ValueError('The existing torrent does not match this file name. No rehash was started.')
    try:
        matches = metadata.verify_filesize(source, allowed_root=allowed_root)
    except OSError:
        matches = False
    if not matches:
        raise ValueError('The existing torrent does not match the local file paths and sizes. Upload stopped; no rehash was started.')
    # Wrapping a hybrid single-file torrent would require changing its v2 tree too.
    if b'files' not in meta[b'info'] and b'meta version' in meta[b'info']:
        raise ValueError('Single-file hybrid torrents cannot be wrapped for reuse. No rehash was started.')
    from utils.unrar_upload_utils import is_archive_path
    if any(is_archive_path(p) for p in metadata.files):
        raise ValueError('Packed torrents are unsupported here. Choose an existing torrent for the unpacked data. No rehash was started.')
    return metadata


def prepare(original,directory,target,allowed_root=None):
    metadata=validate(original,directory,allowed_root=allowed_root)
    meta,_=decode(metadata.raw);info=meta[b'info']
    # A single-file download is kept in a release directory by the import UI.
    # Wrap that same file without changing its piece hashes or byte order.
    if b'files' not in info and Path(directory).is_dir():
        info[b'files']=[{b'length':info.pop(b'length'),b'path':[metadata.name.encode('utf-8')]}]
    info[b'name']=Path(directory).name.encode('utf-8');info.pop(b'name.utf-8',None)
    clean={b'info':info}
    if b'piece layers' in meta:clean[b'piece layers']=meta[b'piece layers']
    Path(target).write_bytes(encode(clean))
    return metadata
