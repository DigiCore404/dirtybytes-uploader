"""Bounded HTTPS downloads with public DNS addresses pinned for the TLS connection."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlparse, urljoin, parse_qs

CATALOGUE_HOSTS = frozenset({'jeedoo.com','adultdvdempire.com','store.freeones.com','en.erotik.com','asiacollection.net','iafd.com','egafd.com','adultfilmdatabase.com','data18.com','m.aebn.net','themoviedb.org','adultboxcovers.com','store18.com'})


def validate_url(url, allowed_hosts=None):
    parsed=urlparse(url)
    host=(parsed.hostname or '').lower().removeprefix('www.')
    if parsed.scheme!='https' or not host or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None,443) or any(c in url for c in '\r\n\x00'):
        raise ValueError('Use a complete public HTTPS URL without login information.')
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError('This catalogue is not supported. Choose one of the listed sources.')
    return parsed


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host,timeout=timeout,context=ssl.create_default_context())
        self.address=address
    def connect(self):
        self.sock=socket.create_connection((self.address,443),self.timeout)
        try:self.sock=self._context.wrap_socket(self.sock,server_hostname=self.host)
        except Exception:
            self.sock.close();raise


def download(url, allowed_hosts=None, limit=2*1024*1024, source_session=False):
    original_host=validate_url(url,allowed_hosts).hostname
    for _ in range(4):
        parsed=validate_url(url,allowed_hosts)
        try:
            addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)))
            if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
                raise ValueError('Private, local and reserved network addresses are not allowed.')
            address=next((ip for ip in addresses if ':' not in ip),addresses[0])
            connection=PinnedHTTPS(parsed.hostname,address,20)
            try:
                target=parsed.path or '/'
                if parsed.query:target+='?'+parsed.query
                headers={'User-Agent':'Mozilla/5.0 (compatible; DirtyBytesMetadata/2.10)','Accept-Language':'en-US,en;q=0.8','Accept-Encoding':'identity'}
                if source_session and parsed.hostname==original_host:
                    from utils.catalogue_sessions import cookie_for
                    cookie=cookie_for(parsed.hostname)
                    if cookie:headers['Cookie']=cookie
                connection.request('GET',target,headers=headers)
                response=connection.getresponse()
                if response.status in (301,302,303,307,308):
                    next_url=urljoin(url,response.getheader('Location') or '')
                    if source_session and validate_url(next_url,allowed_hosts).hostname!=original_host:
                        raise ValueError('Catalogue redirected to another host. Open the source manually; no session was forwarded.')
                    url=next_url
                    continue
                if response.status==404 and source_session and parsed.hostname in ('www.jeedoo.com','jeedoo.com') and parsed.path in ('/','/stream-download/','/porn-movies/','/gay-stream-download/','/gay-porn-movies/') and parse_qs(parsed.query).get('search',[''])[0].strip():
                    from bs4 import BeautifulSoup
                    empty_body=response.read(limit+1)
                    if len(empty_body)<=limit and any(h.get_text(' ',strip=True).casefold().startswith('no results for ') for h in BeautifulSoup(empty_body,'html.parser').select('h1')):
                        return b'','text/html',url
                if response.status!=200:
                    raise ValueError('This source returned HTTP '+str(response.status)+'. Open the source manually. If it requires consent or a session, save its cookies under Source access & cookies and retry.')
                if int(response.getheader('Content-Length') or 0)>limit:raise ValueError('This source is too large.')
                body=response.read(limit+1)
                if len(body)>limit:raise ValueError('This source is too large.')
                return body,response.getheader('Content-Type') or '',url
            finally:connection.close()
        except (OSError,http.client.HTTPException) as exc:
            raise ValueError('Could not read this public source. Try another source or enter the details manually.') from exc
    raise ValueError('This source redirected too many times.')


def catalogue_page(url):
    body,mime,final=download(url,CATALOGUE_HOSTS,source_session=True)
    if 'html' not in mime.lower():raise ValueError('This catalogue did not return an HTML page.')
    return {'html':body.decode('utf-8',errors='replace'),'url':final}
