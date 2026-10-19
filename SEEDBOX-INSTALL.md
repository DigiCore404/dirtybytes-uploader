# DirtyBytes Uploader for Linux seedboxes

Runs directly under your own Linux account. Use the browser interface or CLI directly. The browser interface and CLI use the same upload backend and config.ini.
Based on the existing DirtyBytes/DC Uploader backend; attribution remains in the source.

## Library: browse and upload

Open **Library** to browse files and release folders on the uploader server.
**Add folder** saves a shortcut to a folder inside the configured content library;
it does not upload files from your PC. With Docker, mount additional media inside
`/content` in your Compose configuration. Without Docker, configure your server's
media root in **Settings → Folders & storage**. **Remove shortcut** only removes
the shortcut and leaves the media in place.

Each row shows the expected category from `filters.json`. Change the category
selector if the result is wrong. Configure and test the rules in **Settings →
Automatic categories · filters.json**: the first matching rule wins. Without a
matching rule, choose a category for that item or fix the rules before uploading.
Saved rules also apply to CLI uploads that use automatic category detection;
an explicit CLI `--cat` overrides automatic selection.

Right-click a release, or click its **…** button:

- **Upload Direct** starts immediately with the detected or corrected category.
  Metadata lookup, folder images, screenshots and contact sheets follow your
  saved settings. There is no separate metadata or review prompt.
- **Upload with metadata** opens a dialog to search for metadata or enter details,
  including genres/tags, studio/cast, year, language, description and image URLs.
  You can also correct the category. Entered details take precedence; blank fields
  use automatic detection. Click **Upload with metadata** to start.
- **Test category rules** checks the release name without uploading.
- **Open folder**, **Copy path** and **Refresh** help you browse the library.

Choose an individual release folder or file, not a parent containing unrelated
releases. Single files use the configured hardlink/softlink mode; browsing does
not create links. Follow progress and results in **Activity**. Seed the confirmed
torrent using your configured watch folder or client workflow.

For packs, **Settings → Screenshots & thumbnail sheets → Videos to capture →
Automatic** captures every main video in pack categories and one video in other
categories. **All videos** forces every main video; the screenshot count and
optional MTN contact sheet apply separately to each video.

## 1. Extract and install

Upload the package to a folder you own on the seedbox, then connect over SSH:

```bash
tar -xzf dirtybytes-uploader-seedbox-2.4.1.tar.gz
cd dirtybytes-uploader-seedbox
bash install.sh
```

The ZIP contains the same files if your provider offers a file manager. Keep the
whole directory together. The installer creates a private `.venv`, installs the
pinned Python dependencies, checks media tools and preserves an existing config.ini.
It never starts uploads or modifies your torrent client. Installation needs internet
access to the Python package index, Python 3.10+, venv, FFmpeg/ffprobe and MediaInfo.

No root is needed when the provider supplies those system tools. If Python has a
different name, use `bash install.sh --python /path/to/python3.11`. For missing tools,
ask your seedbox provider. On your own Debian/Ubuntu server you can explicitly use
`bash install.sh --system-deps`; only that option uses sudo/root for system packages.
An installer error means setup is incomplete; fix the reported requirement and rerun.

## 2. Edit config.ini

The included config.ini is a clean example with no credentials. Edit at least:

```ini
[Website]
API_KEY = your-dirtybytes-api-key

[Torrent]
ANNOUNCEURL = your-complete-personal-announce-url

[Paths]
DATADIR = /home/your-user/media
WATCHFOLDER = /home/your-user/watch
```

Replace the paths with your actual directories; do not add quotes. Relative paths
start in the app directory. DATADIR holds release subfolders. WATCHFOLDER receives
small .torrent files, not media. Source files are never moved or renamed. The default
local `content`, `content/incoming` and `watch` folders are created by the installer.
If you choose different folders, create them and give your account the required access.

Set a username and strong password (12–256 characters) in `[Web]`, then start or restart the web service:

```ini
[Web]
USERNAME = admin
PASSWORD = choose-your-own-password
```

A nonempty `PASSWORD` overrides the saved login once. After saving the login in SQLite, the uploader clears `PASSWORD` in config.ini. Later restarts preserve your login and any changes made in Settings. Other settings and upload history are preserved. Keep config.ini private and writable by the uploader.

If PASSWORD is empty and no saved login exists, the first web startup prints a generated login. With a background service, read it using `journalctl --user -u dirtybytes-uploader.service`.


Forgot the workspace password? Stop the web service, then run this from the installation folder:

```bash
bash start.sh reset-password
```

Enter your new password twice, then restart the web service. The command shows your username and preserves settings, uploads and history. It also works before the first web startup.

```bash
bash start.sh check
```

This checks configuration, dependencies and write access without publishing anything.
Optional metadata and image-host keys can be entered later in the browser Settings.

## 3. Open the browser interface

On the seedbox:

```bash
bash start-web.sh
```

It runs headlessly on `127.0.0.1:6080`; keep that SSH session open for now.
On your PC, open a second terminal and establish the tunnel:

```bash
ssh -L 6080:127.0.0.1:6080 your-user@seedbox.example.com
```

Open **http://127.0.0.1:6080** on your PC and sign in. The media stays on the seedbox.
No public port needs opening. The default IP rules allow loopback access through this
tunnel. `bash start-web.sh --port 6081` changes the server port if 6080 is occupied;
adjust the SSH forwarding destination to match.

## 4. Connect qBittorrent and confirm seeding

Add its WebUI URL and credentials in **Clients**, then test the connection. In
**Settings → Download folders & seeding**, save the client and matching paths.
When both programs run on the same native seedbox and see the same filesystem, both
roots can be `/home/your-user/media`. There are no Docker mount names involved.
The mapping test compares existing completed files; a working login alone is not
proof that media is accessible. A remote client on another machine needs shared storage.

- **Import torrent:** choose a source torrent/magnet, client, category and metadata,
  then explicitly enable automatic publication. The running service waits for every
  file, publishes and adds the confirmed DirtyBytes torrent to that client through
  its API with the matching save location. The browser can close.
- **New upload / CLI:** the confirmed torrent goes into WATCHFOLDER. Configure the
  client to watch that same folder and save to the parent of the release. Releases
  in different parent directories need appropriate per-folder save rules or manual
  addition with the correct save location. Connecting a client does not set this up.

Use **Clients** to verify actual checking/seeding status. An accepted site upload and
a seeding client are separate outcomes. Do not republish an accepted upload just
because local torrent delivery needs fixing.

## 5. CLI and optional automatic folder uploads

Preview one release, then publish it explicitly (`9` is Scene/1080p):

```bash
bash start.sh upload /home/your-user/media/My.Release --cat 9 --dry-run
bash start.sh upload /home/your-user/media/My.Release --cat 9
```

`--dry-run` does not upload, hash or contact the tracker. Run
`bash start.sh upload --help` for metadata/image options. Category IDs are in
`files/dirtybytes-categories.json`.

### Recommended for existing downloads: qBittorrent completion command

In the **download client**, enable **Run external program on torrent finished**:

```text
/bin/bash /home/your-user/dirtybytes-uploader/start.sh completed "%F" --cat 9 --hash "%I"
```

Replace the installation path and category. `%F` supplies the completed content path;
`%I` supplies its hash. This is a one-shot process, so no folder watcher or running web
service is required. Test first with the same command plus `--dry-run`.

The callback accepts a complete **release directory or single file** inside DATADIR.
For a single file, it creates a release folder beside the original using the link mode
chosen in Settings. Never pass the entire shared download directory instead.
Folder images/NFOs and screenshot settings supply the description; this command does
not interactively request metadata. The fixed category applies to all callbacks.

Callbacks record source hashes in `data/completions.db` before publication. Repeated
callbacks, failures and interrupted attempts do not automatically repost. Concurrent
callbacks wait up to 30 minutes for the upload lock. Save command output in your process
logs and inspect any failure before retrying. Do not also schedule imports or watch
these same releases.

**Docker:** qBittorrent executes this command inside its own container. The native
command above only works when the installation, Python environment and tools are
available there. Installing the uploader in another container does not provide that
access. Do not mount the Docker socket merely to invoke this command.

### Seed the DirtyBytes torrent in a separate qBittorrent client

Keep the source torrent in the download client. Configure a separate DirtyBytes
seed-client to watch the uploader's **output WATCHFOLDER**. Only confirmed output
torrents go there. Both clients read the same physical media directory:

| Purpose | Generic example |
| --- | --- |
| Host media | `/srv/media/downloads` |
| Media inside both qBittorrent containers | `/downloads` |
| Existing release | `/downloads/My.Release` |
| Save location for the seed-client watch rule | `/downloads` |

Mount the same physical output directory into the uploader and the seed-client's
watch folder. The save location must be the release's **parent**, as seen by the
seed-client. Native installations use actual filesystem paths instead of mount names.
Nested release parents need separate watch rules or manual/API addition with the
correct save location. Let the seed-client verify the existing data before seeding.
Do not enable the completion upload command in the seed-client: that would trigger
another publication attempt. Adding the seed-client in the browser Clients page
provides status monitoring; it does not configure watch rules. Scheduled Import
uploads currently return their torrent to the selected import client.

### Optional: dedicated incoming-folder watcher

To upload prepared folders automatically, create a dedicated incoming folder inside
DATADIR and put one finished release folder inside it:

```bash
mkdir -p /home/your-user/media/incoming
bash start.sh watch --cat 9 --folder incoming
```

Alternatively set `[Watch] INCOMING_DIR = incoming` and omit `--folder`. The seedbox
example already sets this default. **The web service does not start this watcher.**
Every stable release subfolder in the chosen incoming directory is eligible, including
existing ones. Do not watch your entire archive or the same folders as scheduled
imports. A paused copy/download can look stable; add completed content only.
The defaults wait 120 seconds without changes and inspect every 30 seconds.
Keep this command running via your provider's process manager or terminal session.
Attempt state is stored in `data/watch.db`; uncertain/failed attempts never repost
automatically. CLI output/logs and browser Activity are separate records.

## Optional: keep the web service running after logout

If your provider supports systemd user services, run as your ordinary account:

```bash
.venv/bin/python scripts/service.py install
.venv/bin/python scripts/service.py status
journalctl --user -u dirtybytes-uploader.service -n 30
```

Stop a foreground `start-web.sh` process with Ctrl+C before starting the service on
the same port. `install.sh --service` is a convenience for installing and starting
this same user service; it does not start the folder watcher. User lingering and
startup after logout depend on the provider's policy. If systemd user services are
unavailable, use the provider's supported process manager; Docker is not a fallback
requirement. Read the initial generated login in the journal if first startup occurs
as a service.

## Updates and troubleshooting

Stop the uploader before replacing application files. Preserve **config.ini, data/,
watch/, logs/** and your media. In particular, do not overwrite your existing config.ini
with the example included in a new archive. Re-run `bash install.sh` after updating.
It preserves the existing configuration and reuses the virtual environment. Moving
the install directory requires recreating its `.venv` and reinstalling a user service.

If login works but an import cannot see files, check the real paths and permissions
as the uploader's user. If media tools are missing, fix that before using the default
screenshot/MediaInfo options. If an upload is interrupted, check DirtyBytes and the
saved logs/history before any manual retry. No universal default password is shipped.

FFmpeg and MediaInfo remain separately supplied system tools with their own licenses.

## Metadata lookup titles

Settings → Lookup title cleanup contains the words/phrases ignored when looking up
release names in ThePornDB or catalogues. Dots and underscores become spaces.
The search box shows the cleaned title, and direct catalogue URLs pass through unchanged.
Sequel numbers and years are retained unless explicitly listed. This never renames media.
The same list can be edited in config.ini under `[Metadata] SEARCH_IGNORE_WORDS`,
with one indented continuation line per word/phrase. An empty list disables tag removal.


### Configuration in the browser

Settings writes the same config.ini used by the web service and CLI. Screenshots & thumbnail sheets includes MTN sheet/grid/width/footer/font and separate-frame count. Other supported options are grouped below it. Docker-managed mount paths are shown as locked; change those in your container definition. Client credentials and workspace access are managed in their dedicated screens.

Scheduled imports save/export the original torrent and use mkbrr modify without media rehashing. Only trackers, private/source tags, comments and the release wrapper change; file piece hashes remain unchanged. If the source cannot be exported or does not match, the import stops and reports the problem. New manual uploads still use mkbrr create.

## Optional UNRAR / rar2fs

The Docker image already includes these tools. For a native seedbox install, run
`bash install.sh --rar2fs` to compile pinned, checksum-verified rar2fs and UnRAR
sources into `tools/archive`. Build dependencies are a C++ compiler, make,
autoconf/automake/libtool, pkg-config, curl and FUSE development headers. On your
own Debian/Ubuntu machine, `bash install.sh --system-deps --rar2fs` installs them.
On a managed seedbox your provider must supply FUSE support and permit user mounts;
rootless application installation cannot enable a missing host FUSE device.

Choose an archive mount directory outside your media library. The
seeding client must see the same unpacked files and the mount must remain active
while seeding. The hardened systemd user service disallows privilege elevation;
a provider must explicitly permit fusermount if using rar2fs from that service.
Unpacked archives require new torrent hashes; ordinary media imports reuse their
original piece hashes through mkbrr modify.


## Drafts, previews and upload preferences

Use **Save draft** to keep a release and its details without publishing. Open it again from **Drafts**, or choose **Preview without uploading** to generate local screenshots/contact sheets, MediaInfo and a description preview. Preview does not hash a torrent, publish to the site or upload images to an image host. Screenshots are generated again when publishing. CLI `--dry-run` validates and prints the job; it does not generate this full preview.

In **Settings → Single files**, turn **Create release folder** off to upload the original file as a native single-file torrent. Leave it on to create a linked release folder using the selected hardlink/softlink mode. File selection, review and dry-run create no release folders. The posted title excludes the extension; the torrent keeps the original filename for seeding. Screenshots are hosted separately and do not need a release folder.

In **Settings → Folders & seeding**, choose watch-folder delivery or automatic **qBittorrent** delivery. For API delivery, select a client and configure the shared media mapping as seen by both the uploader and qBittorrent. Only the confirmed torrent is added, with the release's parent as its save path. Failed client delivery is shown in Activity and retried without reposting the upload. Automatic background retries run while the web service is running; CLI-only users can retry through Activity when they start it. Normal download imports retain delivery to their selected import client.

Choose **Account preference**, **Anonymous** or **Named** under Upload behaviour. Account preference reads your site's upload privacy setting and stops safely if it cannot be read. Older explicit anonymous configurations retain their privacy until you save a new choice. Required screenshot failures stop publication rather than silently omitting the images.

Use **Changelog** in the sidebar for the full change history. Update instructions include the changelog for a newer stable release when available, with the installed history as a fallback.
