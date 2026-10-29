# Adapted from DigiCore404/blvckout scripts/catalogue_http.py at ea2e241.
# Pure HTML metadata extraction; no worker, database, fetching or credentials.
"""Inert HTML extraction and allowlisted HTTP navigation; no browser or scripts."""
from __future__ import annotations

import datetime
from http.client import HTTPException
import html
import http.cookiejar
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs

from bs4 import BeautifulSoup
from utils.catalogue_text import repair_text


def clean(value):
    text = str(value or '')
    for _ in range(3):
        text = html.unescape(text)
    return ' '.join(repair_text(text).split())


def date(value):
    text = clean(value).replace(',', '').lower()
    months = ['jan january januar', 'feb february februar', 'mar march mär märz maerz',
              'apr april', 'may mai', 'jun june juni', 'jul july juli', 'aug august',
              'sep sept september', 'oct october okt oktober', 'nov november', 'dec december dez dezember']
    try:
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:$|[t\s])', text)
        if match:
            year, month, day = map(int, match.groups())
        elif (match := re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)):
            day, month, year = map(int, match.groups())
        else:
            match = re.fullmatch(r'([a-zäöü.]+) (\d{1,2})(?:st|nd|rd|th)? (\d{4})', text)
            if match:
                name, day, year = match.groups()
            else:
                match = re.fullmatch(r'(\d{1,2})\.? ([a-zäöü.]+) (\d{4})', text)
                if not match:
                    return None
                day, name, year = match.groups()
            month = next(i + 1 for i, names in enumerate(months) if name.strip('.') in names.split())
            day, year = int(day), int(year)
        return datetime.date(year, month, day).isoformat() if 1900 <= year <= datetime.date.today().year + 2 else None
    except (ValueError, StopIteration):
        return None


def names(value):
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(clean(v if isinstance(v, str) else v.get('name', '') if isinstance(v, dict) else '') for v in values if v))


def split_list(value):
    return list(dict.fromkeys(v for v in map(clean, re.split(r'[,|•·;]|\s{2,}', str(value or ''))) if v and len(v) < 60 and v.lower() not in {'and', 'more', 'none', 'n/a', 'unknown'}))


def genre_allowed(name):
    if name.lower() in {'prebooks', 'preorders', 'appearance', 'international', 'feature', '4k ultra hd', 'language', 'french language', 'france', 'character', 'plot oriented', 'settings', 'star showcase', 'age', 'clothing', 'niche'}:
        return False
    return not re.search(r'\bbest\s*sellers?\b|\bclearance\b|\bon sale\b|^(?:dvd|blu[ -]?ray|vod|digital download|4k(?: ultra)? hd|uhd)$|\s[-–/|]\s', name, re.I)


LABELS = {
    'studio': r'studio|studios|distributor|distributed by|production|productions|producer|production company|company|label|brand|network|site',
    'release_date': r'released?|release date|released on|street date|erscheinungsdatum|veröffentlichungsdatum',
    'year': r'released?|release date|released on|year|date|production year',
    'production_year': r'production year|year of production|produktionsjahr',
    'disc_count': r'number of discs|discs?|disc count|anzahl discs|anzahl dvds',
    'barcode': r'upc(?: code)?|ean(?: code)?|barcode|gtin',
    'runtime_minutes': r'length|running time|runtime|minutes|duration|time',
    'performers': r'cast|starring|stars|performers?|actresses|actors|features?|pornstars?',
    'genres': r'categor(?:y|ies)|genres?|keywords?|tags?|themes?|niches?',
}


def pairs(doc):
    result = []
    for row in doc.select('tr'):
        cells = row.find_all(['td', 'th'], recursive=False)
        if len(cells) >= 2:
            result.append((clean(cells[0].get_text(' ', strip=True)).rstrip(':：'), cells[1:], ''))
    for term in doc.select('dt'):
        sibling = term.find_next_sibling()
        if sibling and sibling.name == 'dd':
            result.append((clean(term.get_text()).rstrip(':：'), [sibling], ''))
    for node in doc.select('div,p,li,section'):
        first = node.find(recursive=False)
        if first and first.name in {'strong', 'b'}:
            match = re.fullmatch(r'([A-Za-z][A-Za-z /]{1,24})\s*[:：]', clean(first.get_text()))
            if match:
                value = clean(node.get_text(' ', strip=True))
                result.append((match[1], [node], re.sub(r'^[^:：]+[:：]\s*', '', value)))
    for node in doc.select('p,li,div,span,td,h4,h5,strong,b'):
        if len(node.find_all(recursive=False)) > 3:
            continue
        text = clean(node.get_text(' ', strip=True))
        match = re.fullmatch(r'([A-Za-z][A-Za-z /]{2,24})\s*[:：]\s*(.+)', text) if len(text) <= 400 else None
        if match:
            result.append((match[1], [node], match[2]))
    return result


def absolute(raw, base):
    url = urljoin(base, html.unescape(str(raw or '')))
    parsed = urlsplit(url)
    return url if raw and parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else ''


def cover(element, base):
    if element is None:
        return ''
    image = element.select_one('img')
    source = element.select_one('source[type="image/webp"]')
    srcset = source.get('srcset', '') if source else ''
    candidates = [v.strip().split() for v in srcset.split(',') if v.strip()]
    largest = max(candidates, key=lambda v: float(re.sub(r'[^\d.]', '', v[1]) or 0) if len(v) > 1 else 0)[0] if candidates else ''
    return absolute(element.get('data-href') or element.get('href') or largest or (image and (image.get('data-src') or image.get('src'))), base)


def ade_extras(doc, url):
    """Read only the current product's cast, crew and scene blocks; never fetch clips."""
    product = doc.select_one('.movie-page.itempage') or doc
    directors = list(dict.fromkeys(clean(a.get_text(' ', strip=True)) for a in product.select('a[href*="-directors.html"]') if clean(a.get_text())))[:60]
    people = []
    for image in product.select('img[src*="/actors/"]'):
        anchor = image.find_parent('a')
        if not anchor or not re.fullmatch(r'/\d+/[^/]+-pornstars?\.html', anchor.get('href', '')):
            continue
        name = clean(anchor.get_text(' ', strip=True))
        image_url = absolute(image.get('src'), url)
        if name and image_url and not any(person['name'].casefold() == name.casefold() for person in people):
            people.append(dict(name=name[:120], image_url=image_url, source_url=absolute(anchor['href'], url)))
    # Stable actor links exist even when the source has no portrait.
    for anchor in product.select('a[href*="-pornstar"]'):
        scene_row=anchor.find_parent('div',class_='row')
        if scene_row and scene_row.select_one('a[href*="/clip/"]'):continue
        href=anchor.get('href','');name=clean(anchor.get_text(' ',strip=True))
        if re.fullmatch(r'/\d+/[^/]+-pornstars?\.html',href) and name and not any(p['name'].casefold()==name.casefold() for p in people):
            people.append(dict(name=name[:120],image_url='',source_url=absolute(href,url)))
    scenes = []
    for anchor in product.select('a[href*="/clip/"]'):
        href = anchor.get('href', '')
        if not re.fullmatch(r'/clip/\d+/[^/]+-streaming-scene\.html', href):
            continue
        source_url = absolute(href, url)
        if any(scene['source_url'] == source_url for scene in scenes):
            continue
        row = anchor.find_parent('div', class_='row')
        if row is None:
            continue
        title = clean(anchor.get_text(' ', strip=True))[:240]
        if not title:
            continue
        duration = next((clean(span.get_text()) for span in row.select('span') if re.fullmatch(r'\d+\s*min', clean(span.get_text()), re.I)), '')
        minutes = int(re.search(r'\d+', duration)[0]) if duration else None
        people_in_scene = list(dict.fromkeys(clean(a.get_text(' ', strip=True)) for a in row.select('a[href*="-pornstar"]') if clean(a.get_text())))[:60]
        screenshots = []
        for sibling in row.find_next_siblings():
            if sibling.select_one('a[href*="/clip/"]'):
                break
            for image in sibling.select('a.fancy.screen[href]'):
                target = absolute(image['href'], url)
                if target and target not in screenshots:
                    screenshots.append(target)
        scenes.append(dict(position=len(scenes)+1, title=title, source_url=source_url, runtime_minutes=minutes, performers=people_in_scene, images=screenshots[:2]))
        if len(scenes) == 100:
            break
    return dict(directors=directors, performer_details=people[:60], scenes=scenes, _metadata_version=2)


LANGUAGES={
 'English':'english|englisch|en', 'German':'german|deutsch|de', 'French':'french|französisch|francais|français|fr',
 'Spanish':'spanish|spanisch|español|es', 'Dutch':'dutch|nederlands|holländisch|nl', 'Italian':'italian|italienisch|italiano|it',
 'Portuguese':'portuguese|portugiesisch|português|pt', 'Japanese':'japanese|japanisch|ja', 'Russian':'russian|russisch|ru',
 'Czech':'czech|tschechisch|cs', 'Polish':'polish|polnisch|pl', 'Hungarian':'hungarian|ungarisch|hu',
 'Swedish':'swedish|schwedisch|sv', 'Danish':'danish|dänisch|da', 'Norwegian':'norwegian|norwegisch|no',
 'Finnish':'finnish|finnisch|fi', 'Mandarin':'mandarin|zh', 'Cantonese':'cantonese|kantonesisch', 'Korean':'korean|koreanisch|ko', 'Thai':'thai|th'}
def spoken_languages(doc):
    raw=[]
    # Jeedoo also prints several labelled fields as separate lines in one paragraph.
    for node in doc.select('p,li,td,dd'):
        for line in node.get_text('\n',strip=True).splitlines():
            match=re.fullmatch(r'\s*(?:(?:spoken |audio )?languages?|sprachen?|tonsprachen?)\s*[:：]\s*(.{1,400})',line,re.I)
            if match:raw.append(match[1])
    for label,nodes,value in pairs(doc):
        if re.fullmatch(r'(?:spoken |audio )?languages?|sprachen?|tonsprachen?',label,re.I):raw.append(value or ' '.join(n.get_text(' ',strip=True) for n in nodes))
    for node in doc.select('script[type="application/ld+json"]'):
        try:
            obj=json.loads(node.get_text());items=obj if isinstance(obj,list) else [obj,*obj.get('@graph',[])]
            for item in items:
                if isinstance(item,dict) and re.search('movie|videoobject',str(item.get('@type','')),re.I):raw.extend(names(item.get('inLanguage')))
        except (ValueError,TypeError,AttributeError):pass
    # Explicit language categories count; country labels or performer nationalities do not.
    for a in doc.select('a[href]'):
        if re.search(r'/category/|-porn-categor',a['href'],re.I) and re.fullmatch(r'[A-Za-z]+ Language',clean(a.get_text())):raw.append(clean(a.get_text()).removesuffix(' Language'))
    tokens={v.strip().casefold() for text in raw for v in re.split(r'[,;/|]',text)}
    return [name for name,aliases in LANGUAGES.items() if tokens.intersection(aliases.split('|'))]


def extract(doc, source, url):
    if source == 'store18':
        return store18_metadata(doc, url)
    fields = {}
    images = []
    for script in doc.select('script[type="application/ld+json"]'):
        try:
            parsed = json.loads(script.get_text())
            nodes = parsed if isinstance(parsed, list) else [parsed, *parsed.get('@graph', [])]
            for node in nodes:
                if not isinstance(node, dict) or not re.search(r'movie|videoobject|tvepisode|creativework', str(node.get('@type', '')), re.I):
                    continue
                for key, raw in [('performers', node.get('actor')), ('genres', node.get('genre')), ('studio', node.get('productionCompany') or node.get('publisher'))]:
                    values = [v for v in names(raw) if v]
                    if values:
                        fields.setdefault(key, ', '.join(values) if key != 'studio' else values[0])
                fields.setdefault('release_date', date(node.get('releaseDate') or node.get('datePublished')))
                match = re.search(r'\b(?:19|20)\d{2}\b', str(node.get('datePublished') or node.get('dateCreated') or ''))
                if match:
                    fields.setdefault('year', int(match[0]))
                duration = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?', str(node.get('duration', '')))
                if duration and any(duration.groups()):
                    fields.setdefault('runtime_minutes', int(duration[1] or 0) * 60 + int(duration[2] or 0))
                raw_images = node.get('image', [])
                for value in raw_images if isinstance(raw_images, list) else [raw_images]:
                    images.append(absolute(value if isinstance(value, str) else value.get('url', '') if isinstance(value, dict) else '', url))
        except (ValueError, TypeError, AttributeError):
            continue
    rows = pairs(doc)
    for key, pattern in LABELS.items():
        if fields.get(key) and key != 'release_date':
            continue
        row = next((row for row in rows if re.fullmatch(pattern, row[0], re.I)), None)
        if not row:
            continue
        _, nodes, text = row
        text = text or clean(' '.join(n.get_text(' ', strip=True) for n in nodes))
        linked = list(dict.fromkeys(clean(a.get_text(' ', strip=True)) for n in nodes for a in n.select('a') if 0 < len(clean(a.get_text())) < 60))
        if key == 'release_date':
            fields[key] = date(re.sub(r'^[^:：]+[:：]\s*', '', text)) or fields.get(key)
        elif key in {'year', 'production_year', 'disc_count', 'barcode'}:
            pattern = r'\b(?:19|20)\d{2}\b' if key in {'year', 'production_year'} else r'\b\d{8,14}\b' if key == 'barcode' else r'\b\d{1,3}\b'
            match = re.search(pattern, text)
            if match and (key != 'disc_count' or 0 < int(match[0]) <= 100):
                fields[key] = match[0] if key == 'barcode' else int(match[0])
        elif key == 'runtime_minutes':
            hours = re.search(r'(\d{1,2})\s*(?:h\b|hrs?\.?|hours?)', text, re.I)
            mins = re.search(r'(\d{1,3})\s*(?:m\b|min(?:s|utes)?\.?)', text, re.I)
            number = re.search(r'\b\d{1,4}\b', text)
            total = int(hours[1] if hours else 0) * 60 + int(mins[1] if mins else 0) if hours or mins else int(number[0]) if number else 0
            if 0 < total < 2000:
                fields[key] = total
        elif key in {'genres', 'performers'}:
            fields[key] = ', '.join(linked or split_list(text))
        else:
            fields[key] = (linked or split_list(text) or [''])[0]
    patterns = {'studio': r'/studio/' if source == 'ade' else r'label=', 'performers': r'/\d+/[^/]+-pornstars?\.html' if source == 'ade' else r'actor='}
    if source == 'ade':
        patterns['genres'] = r'/category/|-porn-categor'
    for key, pattern in patterns.items():
        if not fields.get(key):
            values = list(dict.fromkeys(clean(a.get_text(' ', strip=True)) for a in doc.select('a[href]') if re.search(pattern, a['href'], re.I) and 0 < len(clean(a.get_text())) < 60))
            fields[key] = (values or [''])[0] if key == 'studio' else ', '.join(values)
    front = cover(doc.select_one('#front-cover' if source == 'ade' else '#product [data-pp-open="covers"][data-pp-index="0"], .pp-card [data-pp-open="covers"][data-pp-index="0"]'), url)
    back = cover(doc.select_one('#back-cover' if source == 'ade' else '#product [data-pp-open="covers"][data-pp-index="1"], .pp-card [data-pp-open="covers"][data-pp-index="1"]'), url)
    meta = doc.select_one('meta[property="og:image"]')
    if meta:
        images.append(absolute(meta.get('content'), url))
    front = front or next((v for v in images if v), '')
    title_node = doc.select_one('meta[property="og:title"]')
    title = clean(title_node.get('content') if title_node else (doc.select_one('h1') or doc.title).get_text() if (doc.select_one('h1') or doc.title) else '')
    title = re.sub(r'\s*[-–]\s*On Sale!.*$', '', title, flags=re.I)[:240]
    if not title or not (fields.get('studio') or fields.get('performers') or front):
        return None
    if source=='jeedoo':
        fields.pop('release_date',None);fields.pop('year',None)
    return dict(title=title, languages=spoken_languages(doc), release_date=fields.get('release_date'), year=fields.get('year'), production_year=fields.get('production_year'), disc_count=fields.get('disc_count'), runtime_minutes=fields.get('runtime_minutes'), studio=clean(fields.get('studio'))[:160], genres=[v for v in split_list(fields.get('genres')) if genre_allowed(v)][:60], performers=split_list(fields.get('performers'))[:60], front_cover=front, back_cover=back, source_url=url, barcode=fields.get('barcode', ''), notes='', **(ade_extras(doc, url) if source == 'ade' else {}))


def store18_metadata(doc, url):
    """Read the film's metadata, not account notices or recommendation widgets."""
    product = doc.select_one('.video-page')
    heading = product.select_one('.video-title h1.description') if product else None
    if heading is None:
        return None
    details = BeautifulSoup('<h1></h1>', 'html.parser')
    details.h1.string = clean(heading.get_text(' ', strip=True))
    # Only explicitly labelled product fields enter the generic field parser.
    for node in product.select('.studio, .director, .release-date'):
        details.append(BeautifulSoup(str(node), 'html.parser'))
    for anchor in product.select('a[data-category="Item Page"][data-label^="Category"], a[data-category="Item Page"][data-label="Performer"]'):
        details.append(BeautifulSoup(str(anchor), 'html.parser'))
    data = extract(details, 'ade', url)
    if not data:
        return None
    data.pop('_metadata_version', None)
    data['directors'] = list(dict.fromkeys(clean(a.get_text()) for a in product.select('.director a[href]') if clean(a.get_text())))[:60]
    data['performer_details'] = []
    data['performers'] = []
    for anchor in product.select('a[data-category="Item Page"][data-label="Performer"]'):
        name = clean(anchor.get_text(' ', strip=True))
        if not name or name in data['performers']:
            continue
        data['performers'].append(name)
        image = anchor.select_one('img[data-bgsrc], img[data-src]')
        image_url = absolute(image.get('data-bgsrc') or image.get('data-src'), url) if image else ''
        if name:
            data['performer_details'].append(dict(name=name, image_url=image_url, source_url=absolute(anchor.get('href'), url)))
            # The back flag is explicit. Never infer front/back from DOM position or IDs.
    master = ''
    for image in doc.select('#viewLargeBoxcoverCarousel .carousel-item > img'):
        target = absolute(image.get('data-src') or image.get('src'), url)
        parsed = urlsplit(target)
        match = re.fullmatch(r'/movie/(\d+)', parsed.path)
        if not match or parsed.hostname != 'imgs4cdn.adultempire.com':
            continue
        side = 'back_cover' if parse_qs(parsed.query).get('v') == ['back'] else 'front_cover'
        if master and master != match[1]:
            continue
        master = match[1]
        data[side] = target
    data['scenes'] = []
    seen = set()
    for row in doc.select('#scenes article.scene-widget'):
        if not master or row.get('data-master-id') != master:
            continue
        anchor = row.select_one('a.scene-title[href]')
        if not anchor or not re.fullmatch(r'/\d+/[^/]+-streaming-scene-video\.html', anchor['href']):
            continue
        source_url = absolute(anchor['href'], url)
        title = clean(anchor.get_text(' ', strip=True))[:240]
        if not title or source_url in seen:
            continue
        seen.add(source_url)
        length = row.select_one('.scene-length')
        minutes = re.fullmatch(r'(\d+)\s*min', clean(length.get_text()), re.I) if length else None
        cast = list(dict.fromkeys(clean(a.get_text()) for a in row.select('.scene-performer-names a[href]') if clean(a.get_text())))[:60]
        images = list(dict.fromkeys(absolute(i.get('data-src') or i.get('src'), url) for i in row.select('img.screenshot')))[:2]
        data['scenes'].append(dict(position=len(data['scenes'])+1, title=title, source_url=source_url, runtime_minutes=int(minutes[1]) if minutes else None, performers=cast, images=[i for i in images if i]))
        data['performers'] = list(dict.fromkeys([*data['performers'], *cast]))[:60]
        if len(data['scenes']) >= 100:
            break
    data['_physical_edition'] = any(re.match(r'^\s*(?:DVD|Blu[ -]?ray)(?=\s|$)',n.get_text(' ',strip=True),re.I) for n in product.select('#purchase-options h3.price'))
    return data
