# DirtyBytes Uploader changelog

## 2.5.0 · 2026-10-19

- Add persistent upload drafts and a local screenshot, contact-sheet, MediaInfo and description preview without publishing or creating a torrent.
- Add a choice between a linked release folder and a native single-file torrent. Posted titles exclude the file extension; the payload filename is preserved.
- Keep file selection, review and CLI dry-run free of media-folder or link creation.
- Add confirmed torrent delivery to a configured qBittorrent client, visible delivery results and retries without republishing.
- Add Account preference, Anonymous and Named publication settings; stop if the account preference cannot be read.
- Stop uploads when required screenshots cannot be generated, including when no eligible video is found.
- Add Back navigation for visited folders, workspace pages, upload steps, details and dialogs.
- Add a Changelog menu and the complete changelog to update instructions.

## Earlier changes

The entries below preserve the complete change record of this uploader repository. Cosmetic label punctuation changes are excluded.

- 2026-10-17 · Package headless uploader with Docker, native installer and secure publication checks (v2.3.0)
- 2026-10-17 · Return from Activity details and preserve list state; release 2.3.1 (v2.3.1)
- 2026-10-17 · Serve DirtyBytes favicons and browser theme; release 2.3.2
- 2026-10-17 · Simplify installation guide and update bundled torrent and media tools
- 2026-10-17 · Preserve favicon update and prepare uploader release 2.3.3
- 2026-10-17 · Handle MTN warning status only when a complete JPEG was generated (v2.3.3)
- 2026-10-17 · Show CLI uploads in shared Activity history
- 2026-10-17 · Support single-file uploads with selectable hardlinks or softlinks
- 2026-10-17 · Add versioned DirtyBytes uploader footer to upload descriptions
- 2026-10-17 · Clarify first workspace login and add local password recovery
- 2026-10-17 · Allow one-time INI login recovery and document the empty workspace
- 2026-10-17 · Show workspace screenshots in the main README
- 2026-10-17 · Expand README galleries with settings and metadata screenshots
- 2026-10-17 · Fix upload failure recovery, duplicate seeding and UNRAR handling
- 2026-10-18 · Add per-video screenshot mode for packs in web and CLI
- 2026-10-18 · Default to all pack videos and one video for other releases
- 2026-10-18 · Add web release notifications, update instructions and ImgBB support
- 2026-10-18 · Keep ImgBB endpoint and setup help consistent (v2.4.0)
- 2026-10-18 · Fix update panel text contrast for the site theme (v2.4.1)
- 2026-10-18 · Update installation guides to use published latest Docker images
- 2026-10-18 · Organize uploader settings and document direct Compose installation (v2.4.2)
- 2026-10-18 · Make the Image host settings panel collapsible (v2.4.3)
- 2026-10-18 · Add library upload actions, category rules editor and API checks
- 2026-10-18 · Document native FUSE and archive tool requirements
- 2026-10-18 · Release DirtyBytes Uploader 2.4.4 (v2.4.4)
- 2026-10-18 · Document Library uploads and automatic category rules
- 2026-10-18 · Prefer direct TPDB CDN artwork for torrent previews (v2.4.5)
- 2026-10-18 · Center uploader descriptions and remove empty template sections (v2.4.6)
- 2026-10-19 · Reuse existing torrents through Import and CLI without rehash fallback (v2.4.7)
