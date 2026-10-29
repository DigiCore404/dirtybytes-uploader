"""Private, host-scoped user-provided source sessions. Never return cookie values."""
import json, os, re, tempfile, threading
from pathlib import Path
from utils.runtime_tools import ROOT

HOSTS = {'adultdvdempire.com','www.adultdvdempire.com','jeedoo.com','www.jeedoo.com','store.freeones.com','en.erotik.com','store18.com','www.store18.com'}
_lock = threading.RLock()

def path():
    return ROOT/'data/catalogue-sessions.json'

def canonical(host):
    if host not in HOSTS: raise ValueError('Choose a supported source for cookies.')
    return 'www.'+host if host in {'adultdvdempire.com','jeedoo.com','store18.com'} else host

def load():
    try: return json.loads(path().read_text(encoding='utf-8'))
    except FileNotFoundError: return {}

def save(host, value, clear=False):
    host=canonical(host)
    if not clear and (not value or len(value)>16000 or any(ord(c)<32 or ord(c)>126 for c in value) or not all(re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+=[^;]*",part.strip()) for part in value.split(';'))):
        raise ValueError('Paste only the Cookie header value: name=value; name=value. No Cookie: prefix or other headers.')
    with _lock:
        rows=load()
        if clear: rows.pop(host,None)
        else: rows[host]=value.strip()
        target=path();target.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(dir=target.parent,prefix='.catalogue-session-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream: json.dump(rows,stream)
            os.chmod(name,0o600);os.replace(name,target)
        finally:
            Path(name).unlink(missing_ok=True)

def cookie_for(host):
    # Stored apex cookies are explicitly scoped to the normal www catalogue host.
    # A redirect to any other hostname never receives the session.
    return load().get(host,'') if host in HOSTS else ''
