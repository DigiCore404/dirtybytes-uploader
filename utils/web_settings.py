"""Describe and validate every supported config option not managed by a dedicated control."""
import configparser,os,re
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
DEDICATED={('Website','api_key'),('Torrent','announceurl'),('Torrent','hasher'),('Paths','datadir'),('Paths','watchfolder'),('ImageHost','provider'),('ImageHost','api_key'),('ThePornDB','token'),('Metadata','search_ignore_words'),('MediaTools','screenshot_engine')}
DEDICATED|={('Settings',k) for k in ('image_upload','screenshots','mediainfo','dupecheck')}
TITLES={'MediaTools':'Screenshots & thumbnail sheets','Torrent':'Torrent creation & editing','Settings':'Upload behaviour','UploadForm':'DirtyBytes publication','Paths':'Files & folders','ImageHost':'Custom image host','Network':'Network & retries','UnrarUpload':'Archive handling (UNRAR / rar2fs)','Website':'DirtyBytes site','SingleFiles':'Single-file uploads'}
HELP={
 'check_updates':'Check for new stable releases in the web interface. Only the public uploader repository is queried; no configuration or credentials are sent.',
 'link_mode':'Hardlink: no duplicate data, requires the same filesystem. Softlink: a relative link; the original file must remain available to the uploader and seeding client. The release folder is created beside the original file, which stays in place.',
 'screenshot_video_mode':'Automatic (default): all videos for pack categories, one video for other releases. One video: use the first working main video. All videos: create previews for every main video in the release, including subfolders. Sheet and separate screenshot counts apply to each video. Used by both web and CLI.',
 'screenshot_sheet':'Generate one contact sheet per selected video. Requires the MTN engine.',
 'screenshot_singles':'Number of separate screenshots, in addition to the MTN sheet (0–12). FFmpeg needs at least 1.',
 'mtnwidth':'Width of the generated sheet in pixels (320–7680).',
 'mtnsetting':'MTN layout flags. Example: -c 2 -r 8 -D 8 creates a two-column, eight-row sheet. See the installed MTN help for supported layout flags.',
 'mtnpostby':'Text printed beneath the MTN sheet. Plain text or legacy -T "text" syntax.',
 'mtnfontfile':'Optional font path on the uploader server. Empty uses the bundled font.',
 'mtnbin':'Optional MTN executable path. Empty detects the system or bundled tool.',
 'mkbrr_bin':'Optional mkbrr executable path. Empty detects the system or bundled tool.',
 'edit_torrent':'For manual/CLI uploads, reuse a matching torrent from Source folder. Scheduled imports always edit their original source torrent.',
 'sourcefolder':'Existing .torrent files for manual/CLI editing, named Release.Name.torrent. Scheduled imports get their source directly from qBittorrent.',
 'ecomment':'Comment written to the resulting torrent.', 'esource':'Private source tag written to the torrent. Changing this changes its info hash.',
 'creator':'Creator text for generated torrents.',
 'screenshot_categories':'Comma-separated DirtyBytes category IDs that generate screenshots. Other categories skip them.',
 'mediainfo_categories':'Comma-separated category IDs that include technical MediaInfo.',
 'screenshot_sample_fallback':'Allow sample video only when there is no main video.',
 'require_screenshots':'Stop publication when requested screenshots cannot be generated.',
 'include_nfo':'Include the folder NFO once, preserving its formatting.',
 'prependname':'Prefix for delivered .torrent filenames. Media filenames are unchanged.',
 'cleanup':'Remove per-upload temporary files after processing; media is preserved.',
 'dupedl':'Download the existing DirtyBytes torrent when a duplicate is found.',
 'addfastresume':'Add client-specific fast-resume data. Off is recommended; let qBittorrent recheck.',
 'watchfolder_fallback_plain':'Allow a plain torrent when fast-resume delivery is unavailable.',
 'watchfolder_fallback_uploaded_torrent':'Allow the locally uploaded torrent as a delivery fallback if the confirmed download fails.',
 'anonymous':'0 publishes under your account; 1 requests anonymous publication.', 'freeleech':'0 or 1, subject to the tracker permissions of your account.',
 'template_path':'Description template on the uploader server. Supports !description!, !nfo! and !screenshots! placeholders.',
 'filters':'JSON release-filter file on the server.', 'tmp_dir':'Uploader scratch directory; separate from media storage.', 'uploadlog':'Uploader log file on the server.',
 'uploadimgurl':'Custom HTTP(S) image upload API endpoint. Used when custom host is selected.', 'authcode':'Legacy image-host authentication. Blank keeps the saved secret.',
 'timeout':'HTTP request timeout in seconds.', 'torrentdownloadretries':'Maximum attempts to fetch the confirmed torrent.', 'torrentdownloadretrydelay':'Seconds between confirmed-torrent download attempts.',
 'verify_ssl':'Verify HTTPS certificates for tracker/image requests.', 'useragent':'HTTP User-Agent sent by the uploader.',
 'siteurl':'Base HTTP(S) website URL.', 'cookie':'Optional source-site session cookie. Blank keeps the saved secret.',
 'enabled':'Mount RAR releases with rar2fs and upload the unpacked media. Requires host FUSE support and the UNRAR Compose override.',
 'mode':'Use unpacked_only to upload extracted media. Imported archive torrents need new hashes for the unpacked files.',
 'title_suffix':'Optional suffix appended to the release title.', 'title_separator':'Separator before the archive title suffix.',
 'rar2fs_bin':'rar2fs executable on this server.', 'mount_options':'Arguments passed to rar2fs for archive mounts.',
 'mount_base':'Server directory containing archive mounts.', 'categories':'Comma-separated categories eligible for archive processing; empty uses the backend defaults.',
 'ratio_target':'Seeding ratio required before eligible archive cleanup.', 'registry':'Persistent archive-mount registry file.',
 'log':'Archive-processing log file.', 'cleanup_log':'Archive-cleanup log file.', 'cleanup_after_qbit_remove':'Allow eligible mount cleanup after removing the linked client torrent.',
 'cleanup_grace_seconds':'Wait this many seconds before eligible archive cleanup.', 'keep_failed_mounts':'Keep a failed archive mount for diagnosis.',
 'regenerate_mediainfo':'Regenerate technical information for extracted media.', 'mount_ready_timeout':'Seconds to wait for a new archive mount to become readable.'}
LABELS={'uploadimgurl':'Upload API URL','authcode':'Authorization','nsfw':'Mark images as adult','screenshot_video_mode':'Videos to capture','link_mode':'Link mode for single files','mtnwidth':'Sheet width (pixels)','mtnsetting':'MTN grid & layout','mtnpostby':'Sheet footer','mtnfontfile':'MTN font','mtnbin':'MTN executable','screenshot_sheet':'Thumbnail sheet','screenshot_singles':'Separate screenshots','sourcefolder':'Source torrent folder','mkbrr_bin':'mkbrr executable','esource':'Torrent source tag','ecomment':'Torrent comment','include_nfo':'Include folder NFO'}
BOOL={'true','false'}
RANGES={'screenshot_singles':(0,12),'mtnwidth':(320,7680),'timeout':(1,600),'torrentdownloadretries':(1,100),'torrentdownloadretrydelay':(0,300),'freeleech':(0,1),'anonymous':(0,1),'ratio_target':(0,1000),'cleanup_grace_seconds':(0,86400),'mount_ready_timeout':(1,600)}
def defaults():
 c=configparser.ConfigParser(interpolation=None);c.read(ROOT/'defaults.ini',encoding='utf-8');return c

def schema(config):
 result=[];base=defaults()
 sections=sorted((s for s in base.sections() if s not in ('Header','Metadata','ThePornDB')),key=lambda s:(s!='MediaTools',s))
 for section in sections:
  fields=[]
  for key,default in base.items(section):
   if (section,key) in DEDICATED:continue
   secret=key in ('cookie','authcode')
   kind='boolean' if default.lower() in BOOL else 'number' if key in RANGES or re.fullmatch(r'\d+(\.\d+)?',default or '-') else 'text'
   value=config.get(section,key,fallback=default)
   if key=='mtnwidth':value=re.search(r'\d+',value)[0] if re.search(r'\d+',value) else '1280'
   locked=os.environ.get('DIRTYBYTES_CONTAINER')=='1' and ((section=='Paths' and key in ('tmp_dir','uploadlog')) or (section=='UnrarUpload' and key in ('mount_base','registry','log','cleanup_log')))
   fields.append({'key':key,'label':LABELS.get(key,key.replace('_',' ').capitalize()),'help':HELP.get(key,''),'type':'secret' if secret else kind,'value':'' if secret else value,'saved':bool(value) if secret else False,'locked':locked,'range':RANGES.get(key)})
  if section=='MediaTools':
   for field in fields:
    if field['key']=='screenshot_video_mode':field['type']='select';field['options']=[{'value':'auto','label':'Automatic (packs: all / other: one)'},{'value':'single','label':'One video'},{'value':'all','label':'All videos (packs / site rips)'}]
  if section=='SingleFiles':
   for field in fields:
    if field['key']=='link_mode':field['type']='select';field['options']=[{'value':'hardlink','label':'Hardlink (same filesystem)'},{'value':'softlink','label':'Softlink (relative symbolic link)'}]
  if fields:result.append({'section':section,'title':TITLES.get(section,section),'fields':fields})
 return result

def apply(config,changes):
 if not isinstance(changes,dict):raise ValueError('Invalid settings fields.')
 known={(s['section'],f['key']):f for s in schema(config) for f in s['fields']}
 for section,fields in changes.items():
  if not isinstance(fields,dict):raise ValueError('Invalid settings section.')
  if not config.has_section(section):config.add_section(section)
  for key,value in fields.items():
   field=known.get((section,key))
   if not field or field['locked']:raise ValueError('Unknown or container-managed setting: '+section+'.'+key)
   text=str(value).strip()
   if len(text)>8000 or any(c in text for c in '\r\n\x00'):raise ValueError(field['label']+' must be a single line.')
   if field['type']=='secret' and not text:continue
   if field['type']=='select' and text not in {option['value'] for option in field['options']}:raise ValueError('Choose a supported value for '+field['label']+'.')
   if field['type']=='boolean':
    if text.lower() not in ('true','false'):raise ValueError(field['label']+' must be on or off.')
    text=text.lower()
   if field['type']=='number':
    try:number=float(text)
    except ValueError:raise ValueError(field['label']+' needs a number.')
    low,high=field['range'] or (0,1000000)
    if not low<=number<=high or key!='ratio_target' and not number.is_integer():raise ValueError(field['label']+f' must be between {low} and {high}.')
   if (key.endswith('_categories') or key=='categories') and text:
    if not re.fullmatch(r'\d+(\s*,\s*\d+)*',text):raise ValueError('Categories must be comma-separated IDs.')
   if key.endswith('url') and text:
    parsed=urlparse(text)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:raise ValueError('Enter a complete HTTP(S) URL.')
   if key=='mode' and text not in ('unpacked_only','original_only'):raise ValueError('Choose unpacked_only or original_only.')
   config.set(section,key,text)
