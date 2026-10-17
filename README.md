# DirtyBytes Uploader

A simple HTML upload workspace for DirtyBytes. Open it in your browser, choose an existing release folder on the server, add the details, review and upload. No VNC, desktop environment, Node.js build step or external frontend services.

## Linux / seedbox without Docker

On Debian or Ubuntu, install everything with:

```bash
bash install.sh --system-deps
bash start.sh
```

The system-dependency option needs root/sudo to install Python, FFmpeg and MediaInfo. If these are already provided by your seedbox, **no root is needed**:

```bash
bash install.sh
bash start.sh web --host 127.0.0.1 --port 6080 --no-browser
```

Python packages install inside your own `.venv`; Tk is not needed. For a remote seedbox, forward the browser port through your normal SSH account:

```bash
ssh -L 6080:127.0.0.1:6080 your-user@your-seedbox
```

Then open `http://127.0.0.1:6080` on your PC. The HTML interface and upload worker run on the seedbox, so your media stays there. No Docker, VNC or graphical desktop is required. Use the seedbox provider's Python/media tools or ask them to install missing system tools.

Without Docker, use ordinary seedbox paths. For example, set `Paths.DATADIR` to
`/home/your-user/media` and `Paths.WATCHFOLDER` to `/home/your-user/watch`, replacing
`your-user` with your account. When qBittorrent runs on that same seedbox and sees
the same filesystem, both import download roots can be `/home/your-user/media`.
There are no `/content` or `/downloads` mounts unless you create such folders yourself.
Manuals contains separate expandable examples for native seedboxes and Docker,
plus installation, SSH access and optional systemd user-service commands.

## Configuration

The installer creates `config.ini` from `config.example.ini`. The essentials are:

```ini
[Website]
SITEURL = https://dirtybytes.net
API_KEY =

[Torrent]
ANNOUNCEURL =

[Paths]
DATADIR = content
WATCHFOLDER = watch

[Web]
PASSWORD = choose-your-workspace-password
```

Get your API key and personal tracker announce URL from your DirtyBytes account. Relative paths start at the application folder. `DATADIR` contains your release subfolders; `WATCHFOLDER` receives completed tracker torrents. The application never moves or renames your source content.

You can also configure the account, folders and media options in **Settings**. Existing credentials are kept when you leave their fields blank. API keys and announce URLs are never returned to the browser. Advanced defaults live in `defaults.ini`; override individual options in `config.ini`.

## Browser workflow

- **Choose content:** browse the connected server library and choose one release subfolder. The entire library cannot be selected accidentally. The browser shows server folders, not folders on the PC displaying the page.
- **Add the details:** choose a DirtyBytes category; optionally enter studio, performers, genres/tags, year, description and image URLs. BBCode is supported. Leaving image URLs empty uses cover/images in the release folder.
- **Review & upload:** inspect the folder, content size, metadata, description and image handling before publication. The final upload button is available once configuration and content checks pass.
- **Activity:** follow live worker output and view recent attempts. Accepted uploads deliver the confirmed tracker torrent into the watch folder. Interrupted or failed attempts are not automatically reposted.

Automatic screenshots, MediaInfo, folder-image uploads and duplicate checking can be enabled in Settings. An optional NFO is included in the description. The existing filename-based metadata detection fills useful fields when available. Genres are sent as DirtyBytes content tags.

Use extracted content. The standard image does not include privileged FUSE/RAR mounts; archives are flagged during review. For a single video, put it in a release folder. Read-only media is supported.

## Docker / Synology

See [the Docker installation guide](README-docker.md) for the prebuilt image, Compose installer, persistent storage and optional UNRAR / rar2fs setup.

## History and qBittorrent clients

The browser talks to the local Python API, which starts the existing `backend.py` worker as a subprocess. The worker sends structured phase/result events back to the API. The API commits these, along with redacted log lines, to SQLite as they arrive.

`data/uploads.db` contains `upload_jobs`, `upload_job_logs` and `upload_job_events`. Each attempt has its own ID, metadata, source folder, start/end timestamps, status, phase, exit code, error, confirmed torrent ID, torrent hash and watch-torrent location. Existing backend `uploads` records are preserved in their original table. Old browser JSON history is imported once and kept as a backup. All attempts remain stored; Activity supports status filters and loading older pages.

Running jobs become **interrupted** after a restart and are never automatically reposted. An upload accepted by DirtyBytes is recorded separately from local torrent-download/watch-folder success. Logs are committed while the upload runs, rather than only at completion. The browser displays the latest 1,000 lines; all lines remain in SQLite.

Open **Clients** to add multiple qBittorrent WebUI endpoints (NAS, seedbox, or another machine). Enter a name, full WebUI URL, username and password. Save tests the connection; credentials remain on the server and are never returned to the browser. Client definitions and torrent snapshots are stored in the same private SQLite database.

The app reads each enabled client every 30 seconds. The Clients page supports searching, filtering, and pause/resume for individual torrents with qBittorrent 4 and 5. Disconnecting a client removes the saved connection and cached snapshot only; its torrents and files are untouched. No delete-files or bulk-stop action is offered.

History links a release to clients using the **exact hash of the confirmed tracker torrent**, never its name. A watch-folder delivery alone is not described as seeding. Seeding, downloading, checking, paused, queued, not found and unavailable states come from the actual client API. Offline/disabled clients or snapshots older than 90 seconds are marked stale. The client API state mapping follows the [official qBittorrent WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29).

Adding a client monitors and manages its existing torrents; it does not automatically add new uploads to it. Configure the correct watch folder and save-path mappings for each client separately. The app does not change those settings on your behalf.

The interface uses larger, scalable text and controls, with layouts for 1080p and 4K desktops as well as smaller browser windows.

## Torrent client / watch folder

**Settings → Download folders & seeding** explains both delivery routes and saves the
default import client, its download root, and the matching uploader root. The test
button connects to that client and checks names and sizes against existing completed
torrent files. It reports **unverified** when there is no sample, rather than treating
a working login as proof that storage is shared. Every import validates its files again.
These defaults can be overridden per import; recheck them when switching clients.

For example, the host folder `/srv/media/downloads` may be mounted as `/downloads`
in qBittorrent and `/content` in the uploader. Save `/downloads` and `/content` as the
two roots. Do not enter the host path inside a container unless it is mounted there.
The persisted defaults are `[Imports] CLIENT_ID`, `REMOTE_ROOT`, and `LOCAL_ROOT` in
private `config.ini`. An empty local root uses `Paths.DATADIR`.

There are two separate ways to start seeding:

- **Scheduled imports:** after a confirmed upload, the service adds the new DirtyBytes
  torrent to the selected download client through its API, with the matching save path
  and original torrent layout. This flow does not need a shared watch folder. The web
  service must stay running; the browser can close. Resuming a known cancelled import
  can reuse its isolated download directory. If that folder was already uploaded
  manually, the completed job is linked instead of publishing again.
- **New upload and CLI:** the confirmed `.torrent` is written to `Paths.WATCHFOLDER`.
  Configure the client to watch that same physical directory and seed from the correct
  parent of each release. Saving a client connection alone does not enable this route.
  A successful mapping test does not verify the watch directory or its save rules.

Configure your torrent client to watch the host folder mapped to `/watch`. Its save location must be the parent of the selected release folder.

Example: the NAS stores `/srv/media/My.Release`. The uploader sees `/content/My.Release` and writes its torrent to `/watch`. A torrent client running directly on the NAS should save to `/srv/media`; a torrent client in Docker must use its own matching media mount. The generated torrent cannot configure those client mappings for you.

Automatic fastresume is off. Let your client recheck the existing content, and keep the source files available for seeding. The watch folder contains torrents, not media. The isolated Synology preview's watch folder is intentionally separate from your production torrent client until configured.

## CLI and folder watcher

The Settings screen includes copyable commands for native Linux and Docker,
plus the distinction between import automation and the CLI watcher. Starting the web
service does **not** start the folder watcher. Do not run a folder watcher over the
same folders as scheduled imports.

Use `bash start.sh` on Linux.

```bash
bash start.sh check
bash start.sh upload My.Release --cat 9 --dry-run
bash start.sh upload /srv/media/My.Release --cat 9 \
  --studio "Studio Name" --performers "Person One, Person Two" \
  --genre "Tag One, Tag Two" --year 2026 \
  --description "A description" --image "https://example.org/cover.jpg"
bash start.sh watch --cat 9
```

Repeat `--image` for multiple URLs. Leave it out for folder images. All 26 category IDs are in `files/dirtybytes-categories.json`. Explicit categories avoid guessing. `check` tests local configuration, dependencies and real write access without contacting DirtyBytes. `--dry-run` makes no network calls, torrent or upload. CLI upload commands publish immediately.

The watcher waits for immediate release subfolders of `DATADIR` to stop changing, then uploads sequentially with the chosen category. `[Watch] INTERVAL_SECONDS` defaults to 30 and `STABLE_SECONDS` to 120. Move fully prepared release folders into the library; a long pause during an unfinished copy could otherwise look like completion. Hidden and symlinked top-level folders are skipped.

Use a dedicated incoming library: existing stable subfolders are also eligible for
publication. The watcher is an explicit long-running command; keep it alive through
your terminal session or service manager. For a separate Docker watcher configuration,
choose a dedicated subfolder such as `/content/incoming`, then run
`docker compose run --rm uploader watch --cat 9 --folder /content/incoming`.
Alternatively set `[Watch] INCOMING_DIR = incoming` in `config.ini`; relative names
start at `DATADIR`. The `--folder` argument overrides this default and must remain
inside the configured content library. Docker keeps its `/content` mount unchanged.
CLI runs use their logs, backend records and `watch.db`; browser attempts use Activity.
The Clients screen always reports actual torrent status by hash.

Each attempt is recorded in `data/watch.db` before publication. Failed or interrupted attempts never automatically retry, even after a restart. Check the site and logs before a manual retry; do not delete the entire database to retry a single release. No background service is installed by the native installer.

## Results, logs and tests

Exit codes: 0 = completed, 10 = duplicate skipped, 1/2 = error or invalid setup. A request error does not prove that nothing was published. If the site accepted an upload but torrent download or watch placement failed, the upload log records the accepted ID. Download that existing torrent manually rather than blindly uploading again.

Logs normally live in `files/`, or `logs/` in Docker. History and watcher state are in `data/`. Keep these and `config.ini` private. The packaged ZIP excludes local credentials, runtime data, Python environments and logs.

Run the offline integration suite:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests exercise real torrent hashing and media tools with mock tracker endpoints, folder images, duplicate handling, uncertain confirmations, invalid torrents, locks, watcher persistence, HTML delivery, login/session protection, settings, folder confinement and the reviewed upload flow. No real tracker uploads are made by the suite.

Based on the existing DirtyBytes/DC Uploader backend, with original attribution retained in the source. Bundled tools retain their own licences.


### Import a torrent from another tracker

Open **Import torrent**, select a v1/hybrid `.torrent` file (up to 4 MB) or a v1 magnet,
choose an enabled qBittorrent client and a DirtyBytes category, and prepare the details.
Confirm automatic publishing, then choose **Download & schedule upload**.

The two download roots must be the same storage location: the first is the path seen
by qBittorrent, the second is its mapped location inside the uploader's content library.
For example, qBittorrent `/downloads/complete` can map to uploader `/content` when both
mount the same NAS folder. Imports go directly into `<configured download folder>/<release>`
subfolder. For remote seedboxes, mount their files into the uploader; a WebUI connection
alone does not transfer files. Docker can keep the content mount read-only because the
qBittorrent client writes the downloads.

The persistent SQLite queue waits until every file (including any skipped files) is
complete and checks file names, sizes and containment in the mapped folder. It then
uses the existing uploader to create a fresh private DirtyBytes torrent; source tracker
URLs and passkeys are never copied into the new torrent or saved in the import queue.
After a successful upload, the confirmed DirtyBytes torrent is added to the same client
with the matching save path for checking and seeding. The original torrent remains.
**Cancel auto-upload** stops pending publication and leaves the original client torrent
and files in place. Download progress is shown in the queue; upload logs and actual
seeding status are available in Activity and Clients. Interrupted publication requires
review instead of an automatic retry that could create a duplicate.

### Optional ThePornDB metadata

Add your own token under Settings, or set `[ThePornDB] TOKEN` in `config.ini`.
**Find metadata** is available in New upload and Import torrent. Search Scenes or Movies,
choose the matching result, then edit the filled studio, performers, genres, year,
description and image URLs. The selected title is included in the description;
original file/folder names are preserved. Category remains your choice.
Only explicit search text is sent to `https://api.theporndb.net`; the token is server-side,
not returned by the API/UI and not included in distribution packages. Lookup uses the
fixed API origin, HTTPS and no redirects. A failed lookup leaves manual entry available.

If a qBittorrent hostname such as `nas.example.lan` works in your browser but not inside
Docker, use its LAN IP or configure that hostname in Docker `extra_hosts`. Successful
qBittorrent 5.2 HTTP 204 login/add responses are supported. Failed credentials disable
the connection until you edit/enable it, preventing repeated failed login attempts.


### Run as a headless Linux service

The browser UI does not need a desktop or VNC. For a regular Linux host with systemd,
install normally, then run as the user who owns the uploader (without sudo):

```sh
.venv/bin/python scripts/service.py install --host 127.0.0.1 --port 6080
journalctl --user -u dirtybytes-uploader.service -n 30
```

The user service starts with `--no-browser`, restarts after failure, uses private temporary
files and restrictive file permissions. `service.py start`, `stop` and `status` manage it.
For direct LAN access choose the server's LAN bind address instead of `127.0.0.1`.
An SSH tunnel works with the loopback default. Startup before user login / surviving
logout requires user lingering; `loginctl enable-linger YOUR_USER` may need an administrator
on a managed host. Synology runs the supplied Docker container as its headless service,
with `restart: unless-stopped`; it does not use this systemd installer.

First-run username defaults to `admin` (`[Web] USERNAME` or `DIRTYBYTES_WEB_USERNAME`).
The initial password comes from `DIRTYBYTES_WEB_PASSWORD`, `[Web] PASSWORD`, or a random
one shown once in the service log. After initialization the private SQLite credentials
are authoritative: changing bootstrap environment variables does not reset the login.
Use **Settings → Workspace access** to change username/password and the IP allowlist.
Access changes require the current password, invalidate all sessions and reject a list
that would exclude the address currently saving it. New passwords require 12–256
characters. Passwords use random salts and PBKDF2-HMAC-SHA256 with 600,000 iterations.
The access list accepts individual IPv4/IPv6 addresses and CIDRs. Empty allows any
reachable IP, with login still required. The service uses the direct peer address and
ignores forwarded-IP headers; a reverse proxy must enforce its own source-IP policy.
Include loopback in a restricted list when using Docker health checks.

For encrypted direct access, supply a trusted PEM certificate and private key:

```sh
.venv/bin/python uploader.py web --host 0.0.0.0 --no-browser --tls-cert /path/fullchain.pem --tls-key /path/privkey.pem
```

The same options are available to the user service through the `DIRTYBYTES_TLS_CERT`
and `DIRTYBYTES_TLS_KEY` environment variables (a systemd user drop-in can set these).
HTTPS sets Secure session cookies. An executable bundle is a separate packaging step;
this service installer currently uses the included Python environment.


### Catalogue metadata helper

The metadata dialog also includes the parsing and title matching from the supplied
DirtyBytes Metadata Helper userscript. Choose ThePornDB, a public catalogue, or the
ordered Jeedoo → ADE → Freeones → Erotik scan. Other supported sources are IAFD, EGAFD,
AdultFilmDatabase, Data18, AEBN, TMDB, Box covers and direct AsiaCollection release URLs.
A catalogue release URL can be pasted directly. The helper reads structured metadata,
labelled details, studio/cast/genre links and cover images; runtime is included when found.
Match scores remain visible and volume numbers affect the score so different volumes
are not treated as confident matches. Unwanted/composite genre filtering is preserved.
Selecting a result fills the editable form; it does not save changes to an existing
DirtyBytes torrent. No Tampermonkey extension, catalogue account cookies or direct
third-party scripts are needed. Login-only pages, JavaScript-only catalogue content,
CAPTCHAs and sources that block the service need manual entry or another source.
The service fetches only approved catalogue hosts, limits HTML to 2 MB, checks every
redirect, rejects non-public DNS addresses and pins the checked address while verifying
TLS against the original hostname. Fetched HTML is parsed as detached data, never inserted
as executable page HTML. No tracker keys, API keys or browser cookies are sent to catalogues.

### Upload images or rehost covers

Settings has an **Image host** selector: the existing DirtyBytes image API or imghost.dev.
For imghost.dev, create your personal API key in that site's account settings and paste
it into Settings. The account password is not used. This Chevereto 4 integration posts
to `https://imghost.dev/api/1/upload` with an `X-API-Key` header, multipart `source`, JSON
responses and NSFW classification. The key stays in private `config.ini`; a blank field
keeps the saved key. An old custom image-host configuration remains supported.

In both release forms, choose **Upload selected files** to add local covers/images, or
**Rehost image URLs** after selecting metadata with covers. Up to 10 PNG/JPEG/GIF/WebP
images can be sent per batch, at most 8 MB each. Rehosting fetches public HTTPS images
with the same DNS/TLS/redirect restrictions before uploading them. Successful links are
kept if another image in the batch fails. These actions publish images to the selected
image host; choosing metadata alone does not rehost anything. Automatic folder images
and generated screenshots use the same host selection. Live imghost uploads require
your API key; automated tests use a simulated image host without publishing test files.
Optional catalogue tests: `node tests/test_catalogue.cjs` (Node is not a runtime dependency).


### Configuration in the browser

Settings writes the same config.ini used by the web service and CLI. Screenshots & thumbnail sheets includes MTN sheet/grid/width/footer/font and separate-frame count. Other supported options are grouped below it. Docker-managed mount paths are shown as locked; change those in your container definition. Client credentials and workspace access are managed in their dedicated screens.

Scheduled imports save/export the original torrent and use mkbrr modify without media rehashing. Only trackers, private/source tags, comments and the release wrapper change; file piece hashes remain unchanged. If the source cannot be exported or does not match, the import stops and reports the problem. New manual uploads still use mkbrr create.
