# DirtyBytes Uploader

Prepare, review and upload torrents to DirtyBytes from a browser or the command line.
Run it on the Linux server or seedbox that holds your media.

## Install with Docker

Install [Docker Engine with Compose v2](https://docs.docker.com/engine/install/)
on Linux x86_64; Synology users need Container Manager.

```bash
mkdir dirtybytes-uploader && cd dirtybytes-uploader
curl -fLO https://github.com/DigiCore404/dirtybytes-uploader/releases/download/v2.3.2/dirtybytes-uploader-docker-2.3.2.tar.gz
tar -xzf dirtybytes-uploader-docker-2.3.2.tar.gz
bash setup.sh --media /srv/media
```

Replace `/srv/media` with your existing media folder. Open `http://127.0.0.1:6080`,
log in as `admin` with the password printed by setup, then open **Settings**.
For direct LAN access add `--bind 0.0.0.0` to setup and use your server's IP.
When running setup as root, add your normal account's `--uid 1000 --gid 1000`.

## Install without Docker

Requires Python 3.10+, venv, FFmpeg/ffprobe and MediaInfo. Use Debian 12+ or Ubuntu 22.04+.

```bash
curl -fLO https://github.com/DigiCore404/dirtybytes-uploader/releases/download/v2.3.2/dirtybytes-uploader-seedbox-2.3.2.tar.gz
tar -xzf dirtybytes-uploader-seedbox-2.3.2.tar.gz
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
