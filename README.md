# DirtyBytes Uploader

Prepare, review and upload torrents to DirtyBytes from a browser or the command line.
Run it on the Linux server or seedbox that holds your media.

## Screenshots

The empty upload workspace:

![Empty upload workspace](docs/images/workspace-empty.jpg)

Built-in installation and seeding guide:

![Built-in manuals and folder mapping](docs/images/manuals.jpg)

### Settings & automation

![Uploader settings and image host](docs/images/settings.jpg)

### Screenshots & thumbnail sheets

![Screenshot and MTN configuration](docs/images/screenshot-settings.jpg)

In **Settings → Screenshots & thumbnail sheets → Videos to capture**, choose
**Automatic** (default: all videos for pack categories, one for other releases),
**One video**, or **All videos (packs / site rips)**. All videos processes
every main video, including subfolders, with separate screenshot counts and an
optional MTN contact sheet for each video. Samples and extras are skipped when
main videos exist. Use the MTN engine for contact sheets; FFmpeg creates separate
screenshots only. These settings apply to browser uploads, imports and CLI uploads.

For CLI configuration:

```ini
[MediaTools]
SCREENSHOT_VIDEO_MODE = auto
SCREENSHOT_ENGINE = mtn
SCREENSHOT_SHEET = true
SCREENSHOT_SINGLES = 3
```

For packs, this creates one sheet and three separate screenshots per video;
other release categories use one video. With required
screenshots enabled, a failed video stops publication; disabling that option
allows partial previews and logs the failed videos.

### Metadata search

![Empty metadata search](docs/images/metadata-search.jpg)

## Install with Docker

Install [Docker Engine with Compose v2](https://docs.docker.com/engine/install/)
on Linux x86_64.

```bash
git clone https://github.com/DigiCore404/dirtybytes-uploader.git
cd dirtybytes-uploader
bash setup.sh --media /srv/media --image ghcr.io/digicore404/dirtybytes-uploader:latest --bind 0.0.0.0
```

Replace `/srv/media` with your existing media folder. Open `http://<server-ip>:6080`,
log in as `admin` with the password printed by setup, then open **Settings**.
Use `--bind 127.0.0.1` instead to restrict access to the server itself.
When running setup as root, add your normal account's `--uid 1000 --gid 1000`.

## Install without Docker

Requires Python 3.10+, venv, FFmpeg/ffprobe and MediaInfo. Use Debian 12+ or Ubuntu 22.04+.

```bash
curl -fLO https://github.com/DigiCore404/dirtybytes-uploader/releases/download/v2.4.1/dirtybytes-uploader-seedbox-2.4.1.tar.gz
tar -xzf dirtybytes-uploader-seedbox-2.4.1.tar.gz
cd dirtybytes-uploader-seedbox
bash install.sh
bash start.sh web --host 127.0.0.1 --port 6080 --no-browser
```

On your own Debian/Ubuntu server, `bash install.sh --system-deps` also installs
missing system packages using sudo. On a managed seedbox, use the provider's tools.

To reach a remote server from your PC, leave the uploader running and open a tunnel:

```bash
ssh -L 6080:127.0.0.1:6080 your-user@your-server
```

Open `http://127.0.0.1:6080` and use the login printed at startup.

## Configure and upload

1. In **Settings**, enter your DirtyBytes API key and full personal announce URL.
2. Set the media and watch folders. Docker uses `/content` and `/watch`; without
   Docker use real server paths, such as `/srv/media` and `/srv/watch`.
3. Choose one release folder, select its category and check the details.
4. Click **Review & upload**. Check **Activity** for the result and start seeding
   the confirmed torrent through your client's watch folder or client setup.

For CLI uploads, use the same settings in `config.ini`. Replace category `9` with
the correct ID from `files/dirtybytes-categories.json`:

```bash
# Review without uploading
bash start.sh upload /srv/media/My.Release --cat 9 --dry-run
# Submit
bash start.sh upload /srv/media/My.Release --cat 9
```

With Docker, replace `bash start.sh` with `docker compose run --rm uploader`
and use `/content/My.Release` instead of the host path.

Media stays in place. The uploader and torrent client must see the same files;
configure matching paths when they use different mounts. Check Activity and the
tracker before retrying an interrupted upload.

Bundled tools: mkbrr 1.27.0 and MTN 3.5.0. Docker also builds rar2fs 1.29.7 and
UnRAR 7.3.1; FFmpeg and MediaInfo come from the image's system packages.
For updates, persistent storage and optional RAR mounts, see [Docker details](README-docker.md).

For a single file, select it in the content browser. The uploader creates a release
folder beside it and adds a link. Choose **Hardlink** or **Softlink** in
**Settings → Single-file uploads**. Hardlinks require the same filesystem;
softlinks require the original file to stay accessible. No file data is copied.
The seeding client must see both the release folder and original media through
the same library mapping. The media mount needs write access to create the folder.

## Updates and image hosts

**Settings → Uploader updates** checks for new stable releases automatically.
When a newer version exists, a banner links to release notes and update steps for
Docker Compose, a Git checkout, or a seedbox package. **Check for updates** checks
again; configuration, credentials and upload history remain on your own server.
New Docker installations follow `latest`; an existing pinned image must be
changed to `latest` in its existing Compose project to follow stable releases.
Older installations need one manual update to gain this notification feature.

Choose **ImgBB** in Settings and enter your ImgBB API key in **Image host API key**.
This applies to browser images, folder images and screenshots from web or CLI.
For CLI configuration:

```ini
[ImageHost]
PROVIDER = imgbb
API_KEY =
```

Fill API_KEY privately with your ImgBB key. To use the site's own image host,
select it in Settings; no separate image-host key is needed.
