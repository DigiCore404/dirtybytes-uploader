"""Ephemeral Chromium page reads, restricted to the selected public catalogue origin."""
import ipaddress
import socket
import threading
import os
from utils.runtime_tools import ROOT
from urllib.parse import urlparse, parse_qs
from utils.public_download import CATALOGUE_HOSTS,validate_url

_lock=threading.BoundedSemaphore(1)



def empty_search_page(status, url, headings):
    """Jeedoo deliberately returns 404 for its normal empty-search page."""
    parsed=urlparse(url)
    return (status==404 and (parsed.hostname or '').lower().removeprefix('www.')=='jeedoo.com'
            and parsed.path in ('/', '/stream-download/', '/porn-movies/', '/gay-stream-download/', '/gay-porn-movies/')
            and bool(parse_qs(parsed.query).get('search', [''])[0].strip())
            and any(text.strip().casefold().startswith('no results for ') for text in headings))


def http_error(status):
    if status==404:return 'Catalogue page not found (HTTP 404). Check the release URL or search by title.'
    if status in (401,403):return f'The catalogue refused access (HTTP {status}). Try another source or ThePornDB.'
    if status==429:return 'The catalogue is limiting requests (HTTP 429). Wait before searching again.'
    return f'The catalogue returned HTTP {status}. Try again later or choose another source.'


def fetch(url, accept_ade_terms=False):
    parsed=validate_url(url,CATALOGUE_HOSTS)
    if (ROOT/'tools/browser').is_dir():os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'tools/browser'))
    try:
        from playwright.sync_api import sync_playwright,Error,TimeoutError
    except ImportError as exc:raise ValueError('Browser lookup is not installed. Run bash install.sh with browser support, or select another source.') from exc
    addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise ValueError('The catalogue must resolve only to public network addresses.')
    address=next((ip for ip in addresses if ':' not in ip),addresses[0])
    if ':' in address:address='['+address+']'
    canonical=parsed.hostname.lower().removeprefix('www.')
    aliases={parsed.hostname,canonical,'www.'+canonical}
    rules=', '.join('MAP '+host+' '+address for host in sorted(aliases))+', MAP * ~NOTFOUND'
    if not _lock.acquire(timeout=30):raise ValueError('The metadata browser is busy. Try again when the other search finishes.')
    try:
        with sync_playwright() as runtime:
            browser=runtime.chromium.launch(channel='chromium',headless=True,args=['--host-resolver-rules='+rules,'--no-proxy-server'])
            try:
                consent_file=ROOT/'data/catalogue-browser/ade.json'
                consent_state=str(consent_file) if canonical=='adultdvdempire.com' and consent_file.is_file() else None
                context=browser.new_context(storage_state=consent_state,service_workers='block',accept_downloads=False,locale='en-US',
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/'+browser.version+' Safari/537.36')
                def route(request_route):
                    request=request_route.request
                    try:
                        target=validate_url(request.url,CATALOGUE_HOSTS)
                        allowed=target.hostname.lower().removeprefix('www.')==canonical and request.resource_type not in ('image','media','font')
                    except ValueError:allowed=False
                    if allowed:request_route.continue_()
                    else:request_route.abort()
                context.route('**/*',route)
                page=context.new_page()
                response=page.goto(url,wait_until='domcontentloaded',timeout=30000)
                if canonical=='adultdvdempire.com' and urlparse(page.url).path.lower().startswith('/ageconfirmation'):
                    if not accept_ade_terms:raise ValueError('ADE requires age/terms confirmation before metadata can be read. Its consent session must be approved on this uploader.')
                    page.get_by_role('button',name='Agree to Terms and Enter the Site',exact=True).click()
                    page.wait_for_url(lambda value:not urlparse(value).path.lower().startswith('/ageconfirmation'),timeout=15000)
                    consent_file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    context.storage_state(path=str(consent_file))
                    consent_file.chmod(0o600)
                    response=page.goto(url,wait_until='domcontentloaded',timeout=30000)
                final=validate_url(page.url,CATALOGUE_HOSTS)
                if final.hostname.lower().removeprefix('www.')!=canonical:raise ValueError('Catalogue redirected outside the selected source.')
                if response and empty_search_page(response.status,page.url,page.locator('h1').all_text_contents()):
                    return {'html':'','url':page.url,'transport':'browser','no_results':True}
                if not response or response.status!=200:raise ValueError(http_error(response.status if response else 'unknown'))
                try:page.wait_for_load_state('networkidle',timeout=5000)
                except TimeoutError:pass
                final=validate_url(page.url,CATALOGUE_HOSTS)
                if final.hostname.lower().removeprefix('www.')!=canonical:raise ValueError('Catalogue redirected outside the selected source.')
                html=page.content()
                if len(html.encode('utf-8'))>2*1024*1024:raise ValueError('The catalogue page is too large.')
                return {'html':html,'url':page.url,'transport':'browser'}
            finally:browser.close()
    except Error as exc:raise ValueError('Chromium could not read this catalogue. Check that browser dependencies are installed and the source is reachable from this server.') from exc
    finally:_lock.release()
