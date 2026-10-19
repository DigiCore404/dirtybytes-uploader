"""Persistent local upload drafts and previews; never publishes or hashes torrents."""
import copy
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
import uuid
import uploader


class DraftStore:
    def __init__(self, workspace):
        self.workspace=workspace;self.history=workspace.history;self.lock=threading.RLock()
        self.images=self.history.path.parent/'draft-previews';self.preview_thread=None
        with self.history.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS upload_drafts(id TEXT PRIMARY KEY, payload TEXT NOT NULL, revision TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'saved', preview TEXT NOT NULL DEFAULT '{}', error TEXT, created REAL NOT NULL, updated REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)")
            db.execute("UPDATE upload_drafts SET state='error',error='Preview interrupted. The draft is saved; generate its preview again.' WHERE state='previewing'")

    def rows(self):
        with self.history.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,state,error,created,updated,payload FROM upload_drafts WHERE deleted=0 ORDER BY updated DESC LIMIT 200')]

    def get(self, identity):
        with self.history.connect() as db:row=db.execute('SELECT * FROM upload_drafts WHERE id=? AND deleted=0',(identity,)).fetchone()
        if not row:raise ValueError('Draft not found.')
        result=dict(row);result['payload']=json.loads(result['payload']);result['preview']=json.loads(result['preview']);return result

    def save(self, data):
        from web import content_path
        config=uploader.load_config();source=content_path(str(data.get('source') or ''),config,allow_file=True)
        if source==Path(config.get('Paths','DATADIR')).resolve():raise ValueError('Choose a release folder or file, not the whole content library.')
        category=data.get('category') or None
        if category is not None and category not in {c['id'] for c in uploader.categories()}:raise ValueError('Choose a valid category.')
        images=data.get('images',[]);metadata=data.get('metadata',{})
        if not isinstance(images,list) or not isinstance(metadata,dict):raise ValueError('Invalid draft details.')
        if len(images)>100 or len(str(data.get('description','')))>30000:raise ValueError('Draft details are too large.')
        for url in images:
            parsed=urlparse(str(url))
            if parsed.scheme not in ('http','https') or not parsed.hostname or any(c in str(url) for c in '[]\r\n'):raise ValueError('Use complete HTTP(S) image URLs.')
        metadata={k:str(v).strip() for k,v in metadata.items() if k in uploader.META_FIELDS and str(v).strip()}
        if any(len(v)>8000 for v in metadata.values()):raise ValueError('Metadata is too long.')
        payload=dict(source=str(source),release_name=source.stem if source.is_file() else source.name,category=category,
                     description=str(data.get('description') or '').strip(),images=images,metadata=metadata)
        encoded=json.dumps(payload,ensure_ascii=False);identity=str(data.get('draft_id') or uuid.uuid4().hex)
        if not re.fullmatch('[a-f0-9]{32}',identity):raise ValueError('Invalid draft ID.')
        with self.lock,self.history.connect() as db:
            row=db.execute('SELECT payload FROM upload_drafts WHERE id=? AND deleted=0',(identity,)).fetchone()
            if data.get('draft_id') and not row:raise ValueError('Draft not found.')
            if row and row['payload']==encoded:return self.get(identity)
            now=time.time();revision=uuid.uuid4().hex
            db.execute("INSERT INTO upload_drafts(id,payload,revision,created,updated) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision,state='saved',preview='{}',error=NULL,updated=excluded.updated",(identity,encoded,revision,now,now))
        return self.get(identity)

    def delete(self, identity):
        self.get(identity)
        with self.history.connect() as db:db.execute('UPDATE upload_drafts SET deleted=1,revision=? WHERE id=?',(uuid.uuid4().hex,identity))
        return {'ok':True}

    def image(self, identity, revision, filename):
        row=self.get(identity)
        if row['revision']!=revision or filename not in {x['name'] for x in row['preview'].get('images',[])}:raise ValueError('Preview image not found.')
        # Worker PID can differ after a service restart; its saved artifact path is private.
        base=Path(row['preview']['image_folder']).resolve()
        path=(base/filename).resolve()
        if not path.is_relative_to(self.images.resolve()) or path.parent!=base or not path.is_file():raise ValueError('Preview image not found.')
        return path.read_bytes()

    def preview(self, identity):
        with self.lock:
            if self.preview_thread is not None and self.preview_thread.is_alive():raise ValueError('A preview is already running. Wait for it to finish.')
            row=self.get(identity)
            with self.history.connect() as db:
                if db.execute("SELECT 1 FROM upload_drafts WHERE state='previewing' AND deleted=0").fetchone():raise ValueError('A preview is already running. Wait for it to finish.')
            config=copy.deepcopy(uploader.load_config());payload=row['payload']
            job=uploader.validate_job(payload['source'],payload['category'],payload['description'],payload['images'],payload['metadata'],config,prepare_files=False)
            # Previews read media and write only to private scratch space. No site/image-host calls.
            work=self.images/identity/row['revision'];work.mkdir(parents=True,exist_ok=True)
            config.set('Paths','TMP_DIR',str(work))
            with self.history.connect() as db:db.execute("UPDATE upload_drafts SET state='previewing',error=NULL WHERE id=?",(identity,))
        def worker():
            try:
                from utils.screenshot_batch import generate_batch
                from utils.screenshot_utils import generate_candidate
                from utils.mediainfo_utils import generate_mediainfo
                from utils.template_utils import prepare_template
                from utils.nfo_utils import process_nfo
                source=Path(job['source']);category=job['category'];pid=str(__import__('os').getpid());scratch=work/pid;scratch.mkdir(parents=True,exist_ok=True)
                screenshots={int(x.strip()) for x in config.get('Settings','SCREENSHOT_CATEGORIES').split(',') if x.strip()}
                enabled=config.getboolean('Settings','SCREENSHOTS') and category in screenshots
                if enabled:generate_batch(source,config,generate_candidate,category_id=category)
                image_folder=scratch/'screens';images=[]
                for p in sorted(image_folder.glob('*.jpg')):
                    images.append({'name':p.name,'url':'/api/drafts/'+identity+'/images/'+row['revision']+'/'+p.name})
                reason=('No screenshots were generated. Required screenshots are disabled; check the media and screenshot settings.' if not images else '') if enabled else 'Automatic screenshots are disabled or this category is excluded in Settings.'
                mediainfo=''
                categories={int(x.strip()) for x in config.get('Settings','MEDIAINFO_CATEGORIES').split(',') if x.strip()}
                if config.getboolean('Settings','MEDIAINFO') and category in categories:
                    file=generate_mediainfo(source,scratch)
                    if file:mediainfo=file.read_text(encoding='utf-8')
                replacements={'!version!':__import__('utils.app_version',fromlist=['VERSION']).VERSION,'!releasename!':job['release_name'],'!description!':job['description'],'!nfo!':'','!imageupload!':'\n'.join('[c][img]'+str(url)+'[/img][/c]' for url in job['images']),'!screenshots!':'\n'.join('[c][img]'+p['url']+'[/img][/c]' for p in images)}
                if config.getboolean('Settings','INCLUDE_NFO',fallback=True):process_nfo(source,replacements,scratch/'preview.log')
                target=scratch/'description.txt';prepare_template(config.get('Paths','TEMPLATE_PATH'),target,replacements)
                result={'job':job,'images':images,'image_folder':str(image_folder),'description':target.read_text(encoding='utf-8'),'mediainfo':mediainfo,'screenshot_note':reason,'note':'Local preview only. Nothing was published, hashed or uploaded to an image host. Screenshots are generated again when you publish.'}
                with self.history.connect() as db:db.execute("UPDATE upload_drafts SET state='ready',preview=?,error=NULL WHERE id=? AND revision=? AND deleted=0",(json.dumps(result),identity,row['revision']))
            except Exception:
                with self.history.connect() as db:db.execute("UPDATE upload_drafts SET state='error',error='Preview failed. Check the media, screenshot engine and screenshot categories. The draft is still saved; nothing was published.' WHERE id=? AND revision=? AND deleted=0",(identity,row['revision']))
        with self.lock:
            self.preview_thread=threading.Thread(target=worker,daemon=True)
            self.preview_thread.start()
        return self.get(identity)
