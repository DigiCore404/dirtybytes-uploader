"""Retry only confirmed torrent delivery; never resubmit an upload to the site."""
from pathlib import Path, PurePosixPath
import threading
import time
import uuid
from utils.torrent_metadata import TorrentMetadata
from utils.qbit_clients import QbitClients


class DeliveryQueue:
    def __init__(self,history,clients=None):
        self.history=history;self.clients=clients or QbitClients(history);self.lock=threading.Lock();self.stop=threading.Event()
        with history.connect() as db:db.execute("CREATE TABLE IF NOT EXISTS confirmed_deliveries(id TEXT PRIMARY KEY,job_id TEXT,source TEXT NOT NULL,torrent_path TEXT NOT NULL,torrent_hash TEXT NOT NULL,client_id TEXT NOT NULL,save_path TEXT NOT NULL,allowed_root TEXT NOT NULL,state TEXT NOT NULL,error TEXT,updated REAL NOT NULL)")

    def enqueue(self,job,config,events,job_id=None):
        if config.get('Delivery','MODE',fallback='watch')!='client':return
        from utils.delivery import remote_root
        client=config.get('Imports','CLIENT_ID',fallback='').strip()
        source=Path(job['source']).resolve();local=Path(config.get('Imports','LOCAL_ROOT',fallback='') or config.get('Paths','DATADIR')).resolve()
        remote=PurePosixPath(remote_root(config.get('Imports','REMOTE_ROOT',fallback='')))
        if not source.is_relative_to(local):raise ValueError('The release is outside the configured qBittorrent local mapping.')
        self.clients._client(client)
        path=Path(events.get('watch_torrent') or '').resolve()
        watch=Path(config.get('Paths','WATCHFOLDER')).resolve()
        if not path.is_relative_to(watch) or not path.is_file():raise ValueError('The confirmed watch torrent is missing.')
        torrent=TorrentMetadata.read(path);hash_value=events.get('torrent_hash')
        if not hash_value or torrent.infohash.lower()!=hash_value.lower():raise ValueError('Confirmed torrent hash does not match the upload result.')
        if not torrent.verify_filesize(source,allowed_root=local):raise ValueError('The local payload no longer matches the confirmed torrent.')
        save=str(remote.joinpath(*source.relative_to(local).parts).parent)
        identity=uuid.uuid4().hex
        with self.history.connect() as db:db.execute('INSERT INTO confirmed_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?)',(identity,job_id,str(source),str(path),hash_value,client,save,str(local),'pending',None,time.time()))
        self.attempt(identity)
        with self.history.connect() as db:return dict(db.execute('SELECT state,error FROM confirmed_deliveries WHERE id=?',(identity,)).fetchone())

    def attempt(self,identity):
        if not self.lock.acquire(blocking=False):return
        try:
            with self.history.connect() as db:row=db.execute("SELECT * FROM confirmed_deliveries WHERE id=? AND state='pending'",(identity,)).fetchone()
            if not row:return
            error=None;state='pending'
            try:
                metadata=TorrentMetadata.read(row['torrent_path'])
                if metadata.infohash.lower()!=row['torrent_hash'].lower() or not metadata.verify_filesize(row['source'],allowed_root=row['allowed_root']):raise ValueError('Payload changed.')
                existing,_=self.clients.import_status(row['client_id'],row['torrent_hash'])
                if not existing:self.clients.add_torrent(row['client_id'],row['torrent_hash'],row['save_path'],raw=metadata.raw)
                state='added'
            except Exception:
                error='Upload accepted and watch torrent retained. qBittorrent delivery is pending; check the client connection and folder mapping. Delivery retries automatically without uploading again.'
            with self.history.connect() as db:db.execute('UPDATE confirmed_deliveries SET state=?,error=?,updated=? WHERE id=?',(state,error,time.time(),identity))
            if row['job_id']:self.history.update(row['job_id'],{'delivery_status':state,'delivery_error':error or ''})
        finally:self.lock.release()

    def tick(self):
        with self.history.connect() as db:identities=[r['id'] for r in db.execute("SELECT id FROM confirmed_deliveries WHERE state='pending' ORDER BY updated LIMIT 20")]
        for identity in identities:self.attempt(identity)

    def start(self):
        def run():
            while not self.stop.is_set():
                try:self.tick()
                except Exception:pass
                self.stop.wait(30)
        threading.Thread(target=run,daemon=True).start()
