"""BLVCKOUT's inert HTML approach over the uploader's DNS-pinned HTTPS transport."""
from urllib.parse import urlparse
from utils.public_download import catalogue_page
from utils.blvckout_catalogue import BeautifulSoup, extract

def fetch(url):
    result=catalogue_page(url)
    doc=BeautifulSoup(result['html'],'html.parser')
    title=doc.title.get_text(' ',strip=True).lower() if doc.title else ''
    if 'ageconfirmation' in urlparse(result['url']).path.lower() or doc.select_one('#ageConfirmationButton, #challenge-form, form[action*="AgeConfirmation"]') or any(v in title for v in ['age verification','age confirmation','just a moment','access denied','verify you are human']):
        raise ValueError('This source requires manual access/consent. Open it in your browser, then add its cookies under Source access & cookies. No confirmation or challenge is automated.')
    host=(urlparse(result['url']).hostname or '').removeprefix('www.')
    source={'adultdvdempire.com':'ade','jeedoo.com':'jeedoo','store18.com':'store18'}.get(host)
    if source:
        data=extract(doc,source,result['url'])
        if data:
            result['metadata']={'title':data['title'],'studio':data.get('studio',''),'performers':', '.join(data.get('performers',[])),'content_tags':', '.join(data.get('genres',[])),'runtime_minutes':data.get('runtime_minutes') or '', 'release_year':data.get('year') or '', 'images':[v for v in [data.get('front_cover'),data.get('back_cover')] if v]}
    result['transport']='http'
    return result
