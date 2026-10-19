"""Opt-in removal rules for completed client torrents; no local media deletion."""
from pathlib import PurePosixPath
import re
import threading
import time


def policy_values(data):
    values={}
    for key in ('enabled','delete_data'):
        value=data.get(key,False)
        if type(value) is not bool:raise ValueError('Auto-removal switches must be on or off.')
        values[key]=value
    for key,maximum in [('seed_hours',87600),('min_seeders',1000000)]:
        try:
            value=float(data.get(key,0) or 0)
            if not 0<=value<=maximum or key=='min_seeders' and not value.is_integer():raise ValueError()
        except (ValueError,TypeError,OverflowError):raise ValueError('Enter valid seed hours and a whole number of seeders.')
        values[key]=value if key=='seed_hours' else int(value)
    values['match']=str(data.get('match','all'))
    if values['match'] not in ('all','any'):raise ValueError('Choose all or any enabled conditions.')
    if values['enabled'] and not (values['seed_hours'] or values['min_seeders']):raise ValueError('Set at least one removal condition.')
    values['category']=str(data.get('category','')).strip()
    values['tracker']=str(data.get('tracker','')).strip().lower()
    if len(values['category'])>100 or any(x in values['category'] for x in '\r\n\x00'):raise ValueError('Enter one client category.')
    if values['tracker'] and not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]{1,5})?',values['tracker']):raise ValueError('Enter only the tracker hostname, without URL paths or passkeys.')
    return values


def eligible(torrent,policy):
    try:
        progress=float(torrent.get('progress',0));size=int(torrent.get('size',0));left=int(torrent.get('amount_left',0))
        if progress!=1 or size<=0 or left!=0:return False
        if str(torrent.get('state','')) not in ('uploading','stalledUP','forcedUP','queuedUP','pausedUP','stoppedUP'):return False
        if policy['category'] and torrent.get('category','')!=policy['category']:return False
        from utils.qbit_clients import tracker_host
        if policy['tracker'] and tracker_host(torrent.get('tracker',''))!=policy['tracker']:return False
        checks=[]
        if policy['seed_hours']:checks.append(float(torrent.get('seeding_time',-1))>=policy['seed_hours']*3600)
        if policy['min_seeders']:checks.append(int(torrent.get('num_complete',-1))>=policy['min_seeders'])
        return bool(checks) and (all(checks) if policy['match']=='all' else any(checks))
    except (ValueError,TypeError,OverflowError):return False


def shared_payload(torrent,others):
    """Unknown or overlapping content roots cannot be removed automatically with data."""
    def path(row):
        value=str(row.get('content_path') or '').replace('\\','/')
        if not value or '..' in PurePosixPath(value).parts:return None
        if re.match(r'^[a-zA-Z]:/',value):value=value.casefold()
        elif not value.startswith('/'):return None
        result=PurePosixPath(value)
        return result if len(result.parts)>1 else None
    own=path(torrent)
    if own is None:return True
    for other in others:
        if other.get('hash')==torrent.get('hash'):continue
        target=path(other)
        if target is None or own.is_relative_to(target) or target.is_relative_to(own):return True
    return False


class CleanupRules:
    def __init__(self,clients):
        self.clients=clients;self.history=clients.history;self.lock=threading.Lock()
        with self.history.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS client_cleanup_policies(id TEXT PRIMARY KEY,client_id TEXT NOT NULL,name TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,delete_data INTEGER NOT NULL DEFAULT 0,seed_hours REAL NOT NULL DEFAULT 0,min_seeders INTEGER NOT NULL DEFAULT 0,match TEXT NOT NULL DEFAULT 'all',category TEXT NOT NULL DEFAULT '',tracker TEXT NOT NULL DEFAULT '',created REAL NOT NULL,updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS client_cleanup_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS client_cleanup_events(id INTEGER PRIMARY KEY,client_id TEXT NOT NULL,hash TEXT NOT NULL,name TEXT NOT NULL,state TEXT NOT NULL,delete_data INTEGER NOT NULL,created REAL NOT NULL,message TEXT NOT NULL,UNIQUE(client_id,hash));""")
            columns={r[1] for r in db.execute('PRAGMA table_info(client_cleanup_events)')}
            for key in ('rule_id','rule_name'):
                if key not in columns:db.execute("ALTER TABLE client_cleanup_events ADD COLUMN "+key+" TEXT NOT NULL DEFAULT ''")
            if not db.execute("SELECT 1 FROM client_cleanup_meta WHERE key='multiple_rules'").fetchone():
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='client_cleanup_rules'").fetchone():
                    db.execute("""INSERT OR IGNORE INTO client_cleanup_policies SELECT 'legacy-'||client_id,client_id,'Removal rule',enabled,delete_data,seed_hours,min_seeders,match,category,tracker,updated,updated FROM client_cleanup_rules""")
                db.execute("INSERT INTO client_cleanup_meta VALUES('multiple_rules','1')")
    def list(self,identity=''):
        with self.history.connect() as db:
            rows=db.execute('SELECT r.*,c.name AS client_name FROM client_cleanup_policies r JOIN qbit_clients c ON c.id=r.client_id '+('WHERE r.client_id=? ' if identity else '')+'ORDER BY r.created,r.id',(identity,) if identity else ()).fetchall()
        result=[dict(r) for r in rows]
        for r in result:r['enabled']=bool(r['enabled']);r['delete_data']=bool(r['delete_data'])
        return result
    def get(self,identity,rule_id=None):
        rows=self.list(identity)
        if rule_id:
            result=next((r for r in rows if r['id']==rule_id),None)
            if result is None:raise ValueError('Removal rule not found on this client.')
            return result
        return rows[0] if rows else dict(id='',client_id=identity,name='Removal rule',enabled=False,delete_data=False,seed_hours=0,min_seeders=0,match='all',category='',tracker='',updated=0)
    def save(self,identity,data):
        import uuid
        self.clients._client(identity);values=policy_values(data)
        name=str(data.get('name') or 'Removal rule').strip()
        if not name or len(name)>100 or any(ord(c)<32 for c in name):raise ValueError('Enter a rule name up to 100 characters.')
        if values['enabled'] and data.get('confirmed') is not True:raise ValueError('Confirm the removal rule and its data handling before enabling it.')
        with self.clients.operation_lock:
            rule_id=str(data.get('rule_id') or '')
            if rule_id:old=self.get(identity,rule_id)
            elif data.get('new_rule') is True:old={}
            else:old=self.get(identity)
            rule_id=old.get('id') or uuid.uuid4().hex;now=time.time()
            if not old.get('id') and len(self.list(identity))>=20:raise ValueError('Use at most 20 removal rules per client.')
            with self.history.connect() as db:
                db.execute("INSERT INTO client_cleanup_policies VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,enabled=excluded.enabled,delete_data=excluded.delete_data,seed_hours=excluded.seed_hours,min_seeders=excluded.min_seeders,match=excluded.match,category=excluded.category,tracker=excluded.tracker,updated=excluded.updated",(rule_id,identity,name,int(values['enabled']),int(values['delete_data']),values['seed_hours'],values['min_seeders'],values['match'],values['category'],values['tracker'],old.get('created',now),now))
        return self.get(identity,rule_id)
    def remove(self,identity,rule_id):
        with self.clients.operation_lock:
            self.get(identity,rule_id)
            with self.history.connect() as db:db.execute('DELETE FROM client_cleanup_policies WHERE client_id=? AND id=?',(identity,rule_id))
        return {'ok':True}
    def first_match(self,identity,torrent):
        return next((r for r in self.list(identity) if r['enabled'] and eligible(torrent,r)),None)
    def preview(self,identity,data):
        values=policy_values(data);client=self.clients._client(identity)
        if not client['enabled']:raise ValueError('Enable this client first.')
        rows=self.clients.live_torrents(client);candidates=[r for r in rows if eligible(r,values)]
        return {'count':len(candidates),'examples':[str(r.get('name','')) for r in candidates[:20]],'shared_data_skips':sum(shared_payload(r,rows) for r in candidates) if values['delete_data'] else 0,'note':'Read-only preview. No torrents or data were removed. Saved rules run in creation order; only the first matching enabled rule applies. Unknown or shared content paths are skipped for automatic data removal.'}
    def events(self,identity=''):
        with self.history.connect() as db:return [dict(r) for r in db.execute('SELECT e.*,c.name AS client_name FROM client_cleanup_events e LEFT JOIN qbit_clients c ON e.client_id=c.id '+('WHERE client_id=? ' if identity else '')+'ORDER BY e.id DESC LIMIT 30',(identity,) if identity else ())]
    def run(self):
        if not self.lock.acquire(blocking=False):return
        try:
            for client in self.clients.all():
                if not client['online']:continue
                budget=5
                for policy in self.list(client['id']):
                    if not policy['enabled'] or budget<=0:continue
                    try:budget-=self.run_client(client,policy,budget)
                    except Exception:continue
        finally:self.lock.release()
    def run_client(self,client,policy,limit=5):
        private=self.clients._client(client['id']);rows=self.clients.live_torrents(private);attempts=0
        for torrent in rows:
            if attempts>=limit:break
            winner=self.first_match(client['id'],torrent)
            if not winner or winner['id']!=policy['id']:continue
            value=str(torrent.get('hash','')).lower()
            if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',value):continue
            if policy['delete_data'] and shared_payload(torrent,rows):continue
            current=self.get(client['id'],policy['id'])
            if not current['enabled'] or current['updated']!=policy['updated']:break
            with self.history.connect() as db:
                inserted=db.execute("INSERT OR IGNORE INTO client_cleanup_events(client_id,hash,name,state,delete_data,created,message,rule_id,rule_name) VALUES(?,?,?,'pending',?,?,?,?,?)",(client['id'],value,str(torrent.get('name','')),int(policy['delete_data']),time.time(),'Removal requested; awaiting confirmation.',policy['id'],policy['name'])).rowcount
            if not inserted:continue
            attempts+=1
            try:
                self.clients.action(client['id'],value,'delete',delete_data=policy['delete_data'],confirm_hash=value,cleanup_policy=policy)
                state='removed';message='Completed torrent removed; '+('client data removal requested.' if policy['delete_data'] else 'data kept.')
            except Exception:
                state='needs_review';message='Could not confirm removal. Check the client. This torrent will not be retried automatically.'
            with self.history.connect() as db:db.execute('UPDATE client_cleanup_events SET state=?,message=? WHERE client_id=? AND hash=?',(state,message,client['id'],value))
        return attempts
