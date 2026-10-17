'use strict';
// Parsing adapted from the user-supplied DirtyBytes Metadata Helper 4.5.1.
(()=>{
const GENRE_SKIP = [
 'appearance', 'international', 'feature', '4k Ultra Hd', 'Language',
 'French Language', 'France', 'Character', 'Plot Oriented', 'Settings',
 'Star Showcase',
];
// Drop combined genres like "Interracial - Asian Girls": the separate parts
// (Interracial, Asian) are almost always already in the list.
const GENRE_NO_COMBOS = true;
const genreAllowed = name => {
 const lower = String(name || '').trim().toLowerCase();
 if (!lower) return false;
 if (GENRE_SKIP.some(skip => skip.toLowerCase() === lower)) return false;
 if (GENRE_NO_COMBOS && /\s[-–/|]\s/.test(name)) return false;
 return true;
};

const clean = s => String(s || '').replace(/\s+/g, ' ').trim();
const absoluteUrl = (url, base) => {
 try { const r = new URL(url, base); return /^https?:$/.test(r.protocol) ? r.href : ''; } catch { return ''; }
};
const tokens = s => clean(s).toLowerCase().replace(/[''`’]/g, '').replace(/[^a-z0-9 ]+/g, ' ').split(/\s+/)
 // Keep single digits: "Xtra 8" and "Xtra 9" are different films.
 .filter(t => (t.length > 1 || /^\d$/.test(t)) && !/^(the|a|an|and|of|vol|part|disc)$/.test(t));
// Symmetric, so a result with an extra word ("... Hardcut") scores below the
// exact title instead of tying with it.
function similarity(a, b) {
 const left = [...new Set(tokens(a))], right = [...new Set(tokens(b))];
 if (!left.length || !right.length) return 0;
 const other = new Set(right);
 let score = (2 * left.filter(t => other.has(t)).length) / (left.length + right.length);
 // "Pound Me Daddy 3" and "Pound Me Daddy" (or "... 2") are DIFFERENT films:
 // when the volume numbers differ, halve the score so the wrong volume can
 // never pass as a confident match. Only 1-3 digit numbers count - longer
 // runs are product IDs in urls (/5123823/...) and years, not volumes.
 const digits = s => tokens(s).filter(t => /^\d{1,3}$/.test(t)).join(',');
 if (digits(a) !== digits(b)) score *= 0.5;
 return score;
}
const pageTitle = doc => clean(
 doc.querySelector('h1')?.textContent
 || doc.querySelector('meta[property="og:title"]')?.getAttribute('content') || doc.title || '')
 .replace(/\s*[-|–•]\s*(IAFD|EGAFD|Data18|AEBN|The Movie Database|TMDB|Adult ?Film ?Database|Internet Adult Film Database|Stream\s*&\s*Download|jeedoo(?:\.com)?).*$/i, '')
 .slice(0, 160);

/* ======================================================================
   The catalogues. A site needs a host, how a release page looks, and how
   to search it. Everything else is handled by the generic extractor.
   ====================================================================== */
const SITES = [
 { name: 'Jeedoo', host: 'www.jeedoo.com',
   release: /\/(?:product|dvd|vod|scene|movie|title|video)s?\/|\/vod_ms_\d+-/,
   releaseMarker: '#product',
   search: q => 'https://www.jeedoo.com/stream-download/?search=' + encodeURIComponent(q),
   covers: '[data-pp-gallery] a[data-pp-open="covers"]', coverScope: '#product, .pp-card',
   performerLinks: /actor=/, studioLinks: /label=/ },
 { name: 'ADE', host: 'www.adultdvdempire.com',
   // product pages: /5112573/neighbor-affair-vol-68-porn-videos.html
   release: /^\/\d+\/.+-porn-(?:videos?|movies?)\.html/,
   search: q => 'https://www.adultdvdempire.com/allsearch/search?view=list&q=' + encodeURIComponent(q),
   // real performer pages carry a numeric id: /17573/name-pornstars.html -
   // without it you catch the sidebar filter links (Age, Niche, $20 to...)
   performerLinks: /\/\d+\/[^\/"']+-pornstars?\.html/i,
   studioLinks: /\/studio\//i,
   genreLinks: /\/category\/|-porn-categor/i },
 { name: 'Freeones', host: 'store.freeones.com',
   // Adult Empire white-label: same URL layout as ADE
   release: /^\/\d+\/.+-porn-(?:videos?|movies?)\.html/,
   search: q => 'https://store.freeones.com/allsearch/search?view=list&q=' + encodeURIComponent(q),
   performerLinks: /\/\d+\/[^\/"']+-pornstars?\.html/i,
   studioLinks: /\/studio\//i,
   genreLinks: /\/category\/|-porn-categor/i },
 { name: 'Erotik', host: 'en.erotik.com',
   // product pages: /crave-media/pound-me-daddy-3 (studio-slug/title-slug)
   release: /^\/(?!pornstar\/|studio\/|category\/|search|info|service|page)[a-z0-9-]+\/[a-z0-9-]+\/?$/i,
   search: q => 'https://en.erotik.com/search?q=' + encodeURIComponent(q),
   performerLinks: /\/pornstar\//i,
   studioLinks: /\/studio\//i,
   genreLinks: /\/category\//i },
 { name: 'AsiaCollection', host: 'www.asiacollection.net',
   // product pages: /artikel/DV168852/en/neighbor-affair-68 - the site has no
   // server-side search, so this only works via the hand-off panel.
   release: /^\/artikel\/[A-Za-z0-9]+\//,
   search: q => 'https://www.asiacollection.net/search?q=' + encodeURIComponent(q),
   performerLinks: /\/pornstar\//i,
   studioLinks: /\/studio\//i },
 { name: 'IAFD', host: 'www.iafd.com', release: /\/title\.rme\//,
   search: q => 'https://www.iafd.com/ramesearch.asp?searchtype=comprehensive&searchstring=' + encodeURIComponent(q),
   performerLinks: /\/person\.rme\//, studioLinks: /\/distrib\.rme\/|\/studio\.rme\// },
 { name: 'EGAFD', host: 'www.egafd.com', release: /\/films\/details\.php/,
   search: q => 'https://www.egafd.com/films/index.php/search/' + encodeURIComponent(q),
   performerLinks: /\/actresses\/details\.php/ },
 { name: 'AFD', host: 'www.adultfilmdatabase.com', release: /\/video\/\d+\//,
   search: q => 'https://www.adultfilmdatabase.com/search/?q=' + encodeURIComponent(q),
   performerLinks: /\/actor\/|\/performer\//, studioLinks: /\/studio\// },
 { name: 'Data18', host: 'www.data18.com', release: /\/(movies|content|scenes)\//,
   search: q => 'https://www.data18.com/search/?k=' + encodeURIComponent(q),
   performerLinks: /\/(name|pornstars?)\//, studioLinks: /\/(studios?|sites?|network)\// },
 { name: 'AEBN', host: 'm.aebn.net', release: /\/movies\/\d+|movieDetail/,
   search: q => 'https://m.aebn.net/search?queryString=' + encodeURIComponent(q),
   performerLinks: /\/stars?\//, studioLinks: /\/studios?\// },
 { name: 'TMDB', host: 'www.themoviedb.org', release: /\/movie\/\d+/,
   search: q => 'https://www.themoviedb.org/search/movie?query=' + encodeURIComponent(q),
   performerLinks: /\/person\/\d+/, studioLinks: /\/company\/\d+/ },
 { name: 'Box covers', host: 'adultboxcovers.com', release: /^\/[^/]+\/.+/, coversOnly: true,
   search: q => 'https://adultboxcovers.com/?s=' + encodeURIComponent(q) }
];

/* ======================================================================
   Generic extractor. Works on any Document, fetched or live.
   ====================================================================== */
const LABELS = [
 { key: 'studio', re: /^(studio|studios|distributor|distributed by|production|productions|producer|production company|company|label|brand|network|site)$/i },
 { key: 'release_year', re: /^(released?|release date|released on|year|date|production year)$/i },
 { key: 'runtime_minutes', re: /^(length|running time|runtime|minutes|duration|time)$/i },
 { key: 'performers', re: /^(cast|starring|stars|performers?|actresses|actors|features?|pornstars?)$/i },
 { key: 'genres', re: /^(categor(?:y|ies)|genres?|keywords?|tags?|themes?|niches?)$/i }
];
const splitList = text => String(text || '').split(/,|\||•|·|;|\s{2,}/)
 .map(clean).filter(p => p && p.length < 60 && !/^(and|more|none|n\/a|unknown)$/i.test(p));

function labelPairs(doc) {
 const pairs = [];
 for (const row of doc.querySelectorAll('tr')) {
  const cells = [...row.children];
  if (cells.length < 2) continue;
  pairs.push({ label: clean(cells[0].textContent).replace(/[:：]\s*$/, ''), nodes: cells.slice(1) });
 }
 for (const term of doc.querySelectorAll('dt')) {
  const value = term.nextElementSibling;
  if (value && value.tagName === 'DD') pairs.push({ label: clean(term.textContent).replace(/[:：]$/, ''), nodes: [value] });
 }
 // ADE-style blocks: <div><strong>Categories:</strong> <a>Age</a>, <a>..</a></div>
 // (the generic loop below skips nodes with many children, so catch these here)
 for (const node of doc.querySelectorAll('div,p,li,section')) {
  const head = node.firstElementChild;
  if (!head || !/^(STRONG|B)$/.test(head.tagName)) continue;
  const label = clean(head.textContent).match(/^([A-Za-z][A-Za-z /]{1,24})\s*[:：]$/);
  if (label) pairs.push({ label: label[1], nodes: [node] });
 }
 for (const node of doc.querySelectorAll('p,li,div,span,td,h4,h5,strong,b')) {
  if (node.children.length > 3) continue;
  const text = clean(node.textContent);
  if (!text || text.length > 400) continue;
  const match = text.match(/^([A-Za-z][A-Za-z /]{2,24})\s*[:：]\s*(.+)$/);
  if (match) pairs.push({ label: clean(match[1]), nodes: [node], text: clean(match[2]) });
 }
 return pairs;
}
function valueFor(pairs, spec) {
 for (const pair of pairs) {
  if (!spec.re.test(pair.label)) continue;
  const names = pair.nodes.flatMap(n => [...n.querySelectorAll('a')])
   .map(a => clean(a.textContent)).filter(n => n && n.length < 60);
  const text = pair.text || clean(pair.nodes.map(n => n.textContent).join(' '));
  if (text || names.length) return { names, text };
 }
 return null;
}
// Structured data is the most reliable source when a site publishes it.
function fromJsonLd(doc) {
 const fields = {};
 const nodes = [];
 for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
  try {
   const parsed = JSON.parse(script.textContent);
   nodes.push(...(Array.isArray(parsed) ? parsed : [parsed, ...(parsed['@graph'] || [])]));
  } catch {}
 }
 const name = v => typeof v === 'string' ? v : (v && v.name) || '';
 const list = v => (Array.isArray(v) ? v : [v]).map(name).filter(Boolean);
 for (const node of nodes) {
  if (!node || !/movie|videoobject|tvepisode|creativework/i.test(String(node['@type'] || ''))) continue;
  const cast = list(node.actor); if (cast.length) fields.performers ||= [...new Set(cast)].join(', ');
  const genre = list(node.genre); if (genre.length) fields.genres ||= [...new Set(genre)].join(', ');
  const studio = name(node.productionCompany) || name(node.publisher) || name(node.productionCompany?.[0]);
  if (studio) fields.studio ||= studio;
  if (node.description) fields.description ||= String(node.description);
  const date = String(node.datePublished || node.dateCreated || '').match(/\b(?:19|20)\d{2}\b/);
  if (date) fields.release_year ||= date[0];
  const duration = String(node.duration || '').match(/^PT(?:(\d+)H)?(?:(\d+)M)?/);
  if (duration && (duration[1] || duration[2])) fields.runtime_minutes ||= String(Number(duration[1] || 0) * 60 + Number(duration[2] || 0));
  const image = Array.isArray(node.image) ? node.image : [node.image];
  fields._jsonLdImages = image.map(i => typeof i === 'string' ? i : (i && i.url) || '').filter(Boolean);
 }
 return fields;
}
// Covers: biggest images, plus og:image and lazy-loading attributes, with
// logos and banners filtered out and front sorted before back.
function coverUrls(doc, baseUrl, site) {
 const seen = new Map();
 const add = (raw, score, hintSource) => {
  const url = absoluteUrl(raw, baseUrl);
  if (!url) return;
  const hint = (url + ' ' + (hintSource || '')).toLowerCase();
  if (/logo|icon|banner|avatar|sprite|button|placeholder|pixel|\bads?[-_./]|blank|spacer/.test(hint)) return;
  const bonus = /cover|box|front|back|art|scan|jacket|sleeve|poster/.test(hint) ? 4 : 1;
  const rank = /front|_a[._]|_1[._]|-1\.|f\.jpg/.test(hint) ? 0
   : /back|rear|_b[._]|_2[._]|-2\.|b\.jpg/.test(hint) ? 1 : 2;
  const total = Math.max(score, 1) * bonus;
  const previous = seen.get(url);
  if (!previous || previous.score < total) seen.set(url, { url, score: total, rank });
 };
 for (const meta of doc.querySelectorAll('meta[property="og:image"],meta[name="twitter:image"]'))
  add(meta.getAttribute('content'), 400000, 'cover');
 if (site && site.covers && site.coverScope) {
  const scope = doc.querySelector(site.coverScope);
  if (scope) [...scope.querySelectorAll(site.covers)]
   .sort((a, b) => Number(a.getAttribute('data-pp-index') || 0) - Number(b.getAttribute('data-pp-index') || 0))
   .forEach((slide, index) => {
    const source = slide.querySelector('source[type="image/webp"]');
    const image = slide.querySelector('img');
    const candidate = (source && widestFromSrcset(source.getAttribute('srcset')))
     || slide.getAttribute('href') || (image && image.getAttribute('src')) || '';
    add(candidate, 1000000 - index, 'cover');
   });
 }
 for (const image of [...doc.images]) {
  const width = image.naturalWidth || Number(image.getAttribute('width')) || 0;
  const height = image.naturalHeight || Number(image.getAttribute('height')) || 0;
  const hint = (image.alt || '') + ' ' + (image.className || '');
  const area = width * height;
  // A fetched page has no layout, so size is often unknown; keep those images
  // when the url or alt text says it is a cover.
  if (area && (width < 150 || height < 150)) continue;
  if (!area && !/cover|box|front|back|art|poster|jacket|sleeve/i.test(hint + ' ' + (image.getAttribute('src') || ''))) continue;
  const link = image.closest('a[href]');
  const full = link && /\.(jpe?g|png|webp|gif)(\?|$)/i.test(link.getAttribute('href') || '') ? link.getAttribute('href') : '';
  const lazy = image.getAttribute('data-src') || image.getAttribute('data-original') || image.getAttribute('data-lazy-src') || '';
  add(full || widestFromSrcset(image.getAttribute('srcset')) || lazy || image.getAttribute('src'), area, hint);
 }
 return [...seen.values()].sort((a, b) => a.rank - b.rank || b.score - a.score).slice(0, 8).map(e => e.url);
}
function widestFromSrcset(srcset) {
 let best = '', score = -1;
 for (const candidate of String(srcset || '').split(',')) {
  const [url, descriptor = ''] = clean(candidate).split(/\s+/);
  if (!url) continue;
  const value = descriptor.endsWith('w') ? parseFloat(descriptor) : descriptor.endsWith('x') ? parseFloat(descriptor) * 1000 : 0;
  if (value >= score) { score = value; best = url; }
 }
 return best;
}
function extractFrom(doc, baseUrl, site) {
 const fields = {};
 if (!site || !site.coversOnly) {
  Object.assign(fields, fromJsonLd(doc));
  const jsonLdImages = fields._jsonLdImages || []; delete fields._jsonLdImages;
  const pairs = labelPairs(doc);
  for (const spec of LABELS) {
   if (fields[spec.key]) continue;
   const value = valueFor(pairs, spec);
   if (!value) continue;
   if (spec.key === 'release_year') {
    const year = value.text.match(/\b(?:19|20)\d{2}\b/); if (year) fields.release_year = year[0];
   } else if (spec.key === 'runtime_minutes') {
    // "2 hrs. 29 mins." / "2 hours 29 min" / "149 min" / plain "149"
    const hours = value.text.match(/(\d{1,2})\s*(?:h\b|hrs?\.?|hours?)/i);
    const mins = value.text.match(/(\d{1,3})\s*(?:m\b|min(?:s|utes)?\.?)/i);
    let total = (hours || mins) ? Number(hours?.[1] || 0) * 60 + Number(mins?.[1] || 0) : 0;
    if (!total) {
     const plain = value.text.match(/\b(\d{1,4})\b/);
     total = plain ? Number(plain[1]) : 0;
    }
    if (total > 0 && total < 2000) fields.runtime_minutes = String(total);
   } else if (spec.key === 'performers' || spec.key === 'genres') {
    const list = value.names.length ? value.names : splitList(value.text);
    if (list.length) fields[spec.key] = [...new Set(list)].join(', ');
   } else {
    const studio = value.names[0] || splitList(value.text)[0] || '';
    if (studio) fields.studio = studio;
   }
  }
  if (!fields.performers && site && site.performerLinks) {
   const names = [...doc.querySelectorAll('a[href]')].filter(a => site.performerLinks.test(a.getAttribute('href') || ''))
    .map(a => clean(a.textContent)).filter(n => n && n.length < 60);
   if (names.length) fields.performers = [...new Set(names)].join(', ');
  }
  if (!fields.studio && site && site.studioLinks) {
   const studio = [...doc.querySelectorAll('a[href]')].filter(a => site.studioLinks.test(a.getAttribute('href') || ''))
    .map(a => clean(a.textContent)).find(Boolean);
   if (studio) fields.studio = studio;
  }
  if (!fields.genres && site && site.genreLinks) {
   const names = [...doc.querySelectorAll('a[href]')].filter(a => site.genreLinks.test(a.getAttribute('href') || ''))
    .map(a => clean(a.textContent)).filter(n => n && n.length < 40);
   if (names.length) fields.genres = [...new Set(names)].join(', ');
  }
  fields.covers = [...new Set([...jsonLdImages.map(u => absoluteUrl(u, baseUrl)).filter(Boolean), ...coverUrls(doc, baseUrl, site)])];
  return fields;
 }
 fields.covers = coverUrls(doc, baseUrl, site);
 return fields;
}


const parse = (html) => new DOMParser().parseFromString(html,'text/html');
const sameHost = (url,site) => new URL(url).hostname.replace(/^www\./,'')===site.host.replace(/^www\./,'');
const normalize = (doc,url,site,query='') => {
 const fields=extractFrom(doc,url,site),title=pageTitle(doc);
 const jeedooId=site.name==='Jeedoo'?new URL(url).pathname.match(/vod_ms_(\d+)-/)?.[1]:null;
 if(jeedooId)fields.covers=(fields.covers||[]).filter(image=>new RegExp('(^|[^0-9])'+jeedooId+'([^0-9]|$)').test(new URL(image,url).pathname));
 const description=fields.description||doc.querySelector('meta[name="description"],meta[property="og:description"]')?.content||'';
 return {source:'catalogue',site:site.name,url,title,score:query?Math.round(similarity(query,title)*100):100,
 description:parse(String(description)).body.textContent.slice(0,30000),images:(fields.covers||[]).filter(u=>!/[\[\]\r\n]/.test(u)).slice(0,8),
 metadata:{studio:fields.studio||'',performers:fields.performers||'',release_year:fields.release_year||'',runtime_minutes:fields.runtime_minutes||'',content_tags:(fields.genres||'').split(',').map(clean).filter(genreAllowed).join(', ')}};
};
async function page(url,fetcher){const result=await fetcher(url);return {doc:parse(result.html),url:result.url};}
async function fromURL(url,fetcher){const site=SITES.find(s=>sameHost(url,s));if(!site)throw new Error('Choose a URL from one of the supported catalogues.');const result=await page(url,fetcher);if(!sameHost(result.url,site))throw new Error('The catalogue redirected to a different source.');return normalize(result.doc,result.url,site);}
async function scan(site,query,fetcher){
 const result=await page(site.search(query),fetcher);
 if(site.release.test(new URL(result.url).pathname)||(site.releaseMarker&&result.doc.querySelector(site.releaseMarker)))return [normalize(result.doc,result.url,site,query)];
 const seen=new Set();const candidates=[];
 for(const a of result.doc.querySelectorAll('a[href]')){const url=absoluteUrl(a.getAttribute('href'),result.url);if(!url||seen.has(url)||!sameHost(url,site))continue;seen.add(url);const path=new URL(url).pathname;if(!site.release.test(path))continue;const title=clean(a.querySelector('img[alt]')?.alt)||clean(a.getAttribute('title'))||clean(a.textContent);const score=similarity(query,title||decodeURIComponent(path).replace(/[-_/]+/g,' '));if(score>=.4)candidates.push({url,score});}
 candidates.sort((a,b)=>b.score-a.score);
 const values=[],failures=[];
 for(const candidate of candidates.slice(0,3)){try{const detail=await page(candidate.url,fetcher);values.push(normalize(detail.doc,detail.url,site,query));}catch(error){failures.push(error.message);}}
 if(!values.length&&failures.length)throw new Error("Matching releases were found, but their details could not be read. "+failures[0]);
 return values;
}
function releaseIdentity(title){return clean(title).normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').split(/\s+/).filter(word=>word&&!['the','a','an','vol','volume','part','disc'].includes(word)).join(' ');}
function sameRelease(left,right){
 if(!releaseIdentity(left.title)||releaseIdentity(left.title)!==releaseIdentity(right.title))return false;
 const a=left.metadata||{},b=right.metadata||{};
 if(a.release_year&&b.release_year&&String(a.release_year)!==String(b.release_year))return false;
 if(a.studio&&b.studio&&releaseIdentity(a.studio)!==releaseIdentity(b.studio))return false;
 return true;
}
function sourceLabel(row){return row.site||'ThePornDB';}
function combine(rows){
 const choices={},metadata={},fieldSources={},images=[],imageSources={};
 for(const key of ['title','studio','performers','content_tags','release_year','runtime_minutes','description']){
  const options=[];
  for(const row of rows){const value=key==='description'?String(row.description||'').trim():clean(key==='title'?row.title:row.metadata?.[key]);if(!value)continue;const existing=options.find(option=>option.value.toLocaleLowerCase()===value.toLocaleLowerCase());if(existing){if(!existing.sources.includes(sourceLabel(row)))existing.sources.push(sourceLabel(row));}else options.push({value,sources:[sourceLabel(row)]});}
  options.sort((a,b)=>b.sources.length-a.sources.length||(['performers','content_tags'].includes(key)?b.value.length-a.value.length:0));
  if(key==='content_tags'&&options.length>1){const tags=new Map();for(const option of options)for(const tag of option.value.split(',').map(clean).filter(genreAllowed))if(!tags.has(tag.toLowerCase()))tags.set(tag.toLowerCase(),tag);const union=[...tags.values()].join(', ');if(union&&!options.some(option=>option.value===union))options.unshift({value:union,sources:[...new Set(options.flatMap(option=>option.sources))]});}
  choices[key]=options;fieldSources[key]=options[0]?.sources||[];metadata[key]=options[0]?.value||'';
 }
 for(const row of rows)for(const url of row.images||[]){if(!imageSources[url])imageSources[url]=[];if(!imageSources[url].includes(sourceLabel(row)))imageSources[url].push(sourceLabel(row));if(!images.includes(url)&&images.length<16)images.push(url);}
 return {source:'catalogue',url:rows.length===1?rows[0].url:undefined,site:[...new Set(rows.map(sourceLabel))].join(' + '),title:metadata.title,description:metadata.description,metadata,images,imageSources,choices,fieldSources,contributions:rows};
}

async function search(query,provider,fetcher,progress){
 if(/^https?:\/\//i.test(query))return {results:[await fromURL(query,fetcher)],errors:[]};
 query=SearchTitles.normalize(query);
 const selected=provider==='auto'?['Jeedoo','ADE','Freeones','Erotik'].map(n=>SITES.find(s=>s.name===n)):SITES.filter(s=>s.name===provider);
 if(!selected.length)throw new Error('Choose a metadata source.');const results=[],errors=[];
 for(const site of selected){progress('Searching '+site.name+'…');try{results.push(...await scan(site,query,fetcher));}catch(error){errors.push(site.name+': '+error.message);}}
 results.sort((a,b)=>b.score-a.score);return {results:results.slice(0,12),errors};
}
window.CatalogMetadata={sites:SITES,search,fromURL,similarity,extract:extractFrom,normalize,sameRelease,combine,sourceLabel};
})();
