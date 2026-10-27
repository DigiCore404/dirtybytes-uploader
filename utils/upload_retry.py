"""Explicit retries from durable inputs; accepted posts are never submitted again."""
import json
from pathlib import Path
import re
import uuid
import requests
import uploader
from utils.torrent_metadata import TorrentMetadata, LIMIT


def get_site(config, path, params=None, binary=False):
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(config.get('Website','SITEURL').rstrip('/') + path,
                params=params, headers={'X-API-KEY':config.get('Website','API_KEY'),'Accept':'application/x-bittorrent' if binary else 'application/json'},
                timeout=30, verify=config.getboolean('Network','VERIFY_SSL',fallback=True), allow_redirects=False, stream=binary)
            if response.status_code != 200:
                raise ValueError('The site check failed (HTTP '+str(response.status_code)+'). Nothing was submitted. Fix the connection and retry.')
            if not binary:
                return response.json()
            chunks=[];size=0
            for chunk in response.iter_content(1024*1024):
                size+=len(chunk)
                if size>LIMIT:raise ValueError('The confirmed torrent download is too large.')
                chunks.append(chunk)
            return b''.join(chunks)
    except (requests.RequestException, json.JSONDecodeError) as exc:
        raise ValueError('The site could not be checked. Nothing was submitted; retry when the API is available.') from exc


def recover(workspace, row, config):
    """Recover only the personalized torrent and client delivery, without hashing."""
    from web import content_path
    source=content_path(row['source'],config,allow_file=True)
    watch=Path(config.get('Paths','WATCHFOLDER')).resolve()
    path=Path(row.get('watch_torrent') or '').resolve()
    if not path.is_absolute() or not path.is_relative_to(watch) or not path.is_file():
        if not row.get('torrent_id'):raise ValueError('The accepted torrent ID is missing. Check the site before retrying.')
        raw=get_site(config,'/api/v1/torrents/download/'+str(int(row['torrent_id'])),binary=True)
        torrent=TorrentMetadata(raw)
        if row.get('torrent_hash') and torrent.infohash.lower()!=row['torrent_hash'].lower():
            raise ValueError('The confirmed torrent hash changed. No files were written or rehashed.')
        if not torrent.private or not torrent.verify_filesize(source,allowed_root=Path(config.get('Paths','DATADIR'))):
            raise ValueError('The confirmed torrent does not match the local files. Nothing was rehashed or published.')
        watch.mkdir(parents=True,exist_ok=True)
        path=watch/(re.sub(r'[^a-zA-Z0-9_-]','_',row['id'])+'.torrent')
        temporary=path.with_suffix('.tmp.'+uuid.uuid4().hex)
        try:temporary.write_bytes(raw);temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
    torrent=TorrentMetadata.read(path)
    if row.get('torrent_hash') and torrent.infohash.lower()!=row['torrent_hash'].lower():
        raise ValueError('The confirmed torrent hash changed. No upload was submitted.')
    if not torrent.private or not torrent.verify_filesize(source,allowed_root=Path(config.get('Paths','DATADIR'))):
        raise ValueError('Local files no longer match the confirmed torrent. No rehash was started.')
    workspace.history.update(row['id'],{'site_status':'accepted','watch_torrent':str(path),'torrent_hash':torrent.infohash,'error':''})
    row=workspace.history.get(row['id'])
    delivery=workspace.deliveries.enqueue(row,config,row,row['id'])
    workspace.history.finish(row['id'],'completed',0,'')
    return {'id':row['id'],'state':'recovered','delivery':delivery,'message':'Confirmed torrent recovered. No upload was posted again.'}


def retry(workspace, identity, confirmed=False):
    with workspace.lock:
        row=workspace.history.get(identity)
        if not row:raise ValueError('Upload not found.')
        if row.get('retry_id'):return {'id':row['retry_id'],'state':'already_retried','message':'Opening the existing retry attempt.'}
        if workspace.active:raise ValueError('An upload is still running. Follow it in Activity.')
        if row['status']=='running':
            # The OS lock, rather than a timestamp, proves no worker owns it.
            with uploader.upload_lock():
                workspace.history.finish(identity,'interrupted',error='The previous worker is no longer running. Retry requested explicitly.')
            row=workspace.history.get(identity)
        if row['status'] not in ('needs_review','interrupted'):
            raise ValueError('Only failed or interrupted uploads can be retried.')
        if row['site_status']=='duplicate':raise ValueError('This release already exists. No new upload was submitted.')
        config=uploader.load_config()
        if row['site_status']=='accepted':
            with uploader.upload_lock():return recover(workspace,row,config)
        payload=row.get('retry_payload')
        legacy=not payload
        if not payload:
            payload={key:row[key] for key in ('source','category','description','metadata','images')}
            payload['post_title']=row['name']
            with workspace.history.connect() as db:
                imported=db.execute('SELECT * FROM torrent_imports WHERE job_id=? OR id=?',(identity,identity)).fetchone()
            if imported:
                payload['source_torrent']=str(workspace.imports._original_torrent(dict(imported)))
                payload['delivery_managed']=True
                legacy=False
        name=payload.get('post_title') or payload.get('release_name') or row['name']
        matches=get_site(config,'/api/v1/torrents_exact_search',{'searchText':name})
        if not isinstance(matches,list) or any(not isinstance(m,dict) or not isinstance(m.get('name'),str) or not str(m.get('id','')).isdigit() or int(m['id'])<=0 for m in matches):
            raise ValueError('The site returned an invalid duplicate check. Nothing was submitted.')
        found=next((m for m in matches if m['name'].casefold()==name.casefold()),None)
        if found:
            if row['site_status'] in ('pending','unknown'):
                workspace.history.update(identity,{'site_status':'accepted','torrent_id':int(found['id']),'torrent_name':name})
                with uploader.upload_lock():return recover(workspace,workspace.history.get(identity),config)
            workspace.history.update(identity,{'site_status':'duplicate','torrent_id':int(found['id']),'torrent_name':found['name']})
            workspace.history.finish(identity,'duplicate',10,'')
            return {'id':identity,'state':'exists','message':'This release already exists on the site. No new upload was submitted.'}
        if not confirmed and (legacy or row['site_status'] in ('pending','unknown')):
            message='The previous publication could not be confirmed. No exact match is currently returned by the site. Check the site before allowing another upload.'
            if legacy:message+=' This older record has no complete retry snapshot; original CLI torrent-reuse details may be missing. A new torrent may be created unless reuse is configured.'
            return {'id':identity,'state':'confirmation_required','message':message}
        result=workspace.review(payload,source_torrent=payload.get('source_torrent'))
        if not result['ready']:raise ValueError('\n'.join(result['errors']))
        job=workspace.drafts[result['review_id']]['job']
        job['retry_of']=identity
        if payload.get('delivery_managed'):job['delivery_managed']=True
        result=workspace.upload(result['review_id'])
        with workspace.history.connect() as db:
            db.execute("UPDATE torrent_imports SET job_id=?,status='uploaded',seed_status='pending',error=NULL WHERE job_id=? OR id=?",(result['id'],identity,identity))
        return dict(result,state='started',message='Retry started with the saved upload details and current settings.')
