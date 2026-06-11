<p align="center">
   <img src="docs/WZML-X.png" alt="WZML-X logo" width="420">
</p>

<h1 align="center">WZML-X</h1>

<p align="center">
   Telegram mirroring and leeching platform with a container-based runtime, a lightweight web UI, and a configurable transfer pipeline.
</p>

<p align="center">
   <a href="https://github.com/SilentDemonSD/WZML-X">
      <img src="https://img.shields.io/github/stars/SilentDemonSD/WZML-X?style=for-the-badge&logo=github&label=Stars" alt="Stars">
   </a>

   <a href="https://github.com/SilentDemonSD/WZML-X/search?l=python">
      <img src="https://img.shields.io/github/languages/top/SilentDemonSD/WZML-X?style=for-the-badge&logo=python&label=Python" alt="Python">
   </a>

   <a href="https://github.com/SilentDemonSD/WZML-X/blob/main/docker-compose.yml">
      <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
   </a>

   <a href="https://t.me/WZML_X">
      <img src="https://img.shields.io/badge/Telegram-Community-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
   </a>

   <a href="https://github.com/SilentDemonSD/WZML-X/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/SilentDemonSD/WZML-X?style=for-the-badge&label=License" alt="License">
   </a>

   <a href="https://github.com/SilentDemonSD/WZML-X/commits/main">
      <img src="https://img.shields.io/github/last-commit/SilentDemonSD/WZML-X?style=for-the-badge&label=Last%20Commit" alt="Last Commit">
   </a>
</p>

## Index

<details open>
   <summary>Table of Contents <kbd>Click Here</kbd></summary>

   - [At a Glance](#at-a-glance)
   - [Why Use It](#why-use-it)
   - [What It Covers](#what-it-covers)
   - [How It Runs](#how-it-runs)
   - [Deployment](#deployment)
   - [Configuration](#configuration)
   - [Project Layout](#project-layout)
   - [Documentation](#documentation)
   - [Support](#support)
   - [Credits](#credits)
   - [License](#license)
- [Video Tools (-vt) Pipeline Deployment Guide](#video-tools--vt-pipeline-deployment-guide)
- [User Settings Import/Export](#user-settings-importexport)
</details>

## Video Tools (-vt) Pipeline Deployment Guide

The Advanced Video Tools (-vt) pipeline allows users to perform multi-select video processing tasks such as merging, muxing audio, compressing to multiple resolutions, and removing specific streams.

### Prerequisites
- **FFmpeg**: Ensure FFmpeg is installed in your environment. The bot uses it for all video processing tasks.
- **Python Dependencies**: All necessary libraries are included in `requirements.txt`.

### Step-by-Step Setup

1. **Deploy the Bot**: Follow the standard WZML-X deployment instructions for VPS or Heroku.
2. **Environment Variables**:
   - No additional environment variables are required for basic `-vt` functionality.
   - Ensure `FFMPEG_NAME` in your config points to the correct FFmpeg binary (default is `ffmpeg`).
3. **Usage**:
   - To use the Video Tools, add the `-vt` flag to your mirror or leech command.
   - Example: `/leech -vt https://link-to-video.mp4` or `/mirror -vt` (as a reply to a file).
   - An interactive menu will appear allowing you to select multiple tools.
4. **Tool-Specific Info**:
   - **Video + Video**: Extracts archives and merges all contained video files alphabetically.
   - **Video + Audio**: Prompts you to send an audio source after the main download completes.
   - **Compress**: Allows selecting multiple resolutions (144p to 1080p) simultaneously.
- **Remove Stream**: Displays all available tracks in the video and lets you select which ones to remove (❌).

## User Settings Import/Export
- **Export Settings**: Click the button in `/uset` to zip all your custom settings (Captions, Thumbnails, Tokens, etc.) and receive it in your PM.
- **Import Settings**: Use the "Import Settings" button in `/uset` and follow the prompt to upload your backup zip file. This restores all settings and files instantly, making bot migration a breeze!

### Troubleshooting
- If FFmpeg fails, check the logs for specific errors. It may be due to incompatible codecs in the source file.
- Ensure the bot has enough disk space for processing, especially when merging or compressing large files.

## At a Glance

| Area | Details |
|---|---|
| Runtime | Python Telegram bot + web UI |
| Deployment | Docker & Docker Compose |
| Required config | `BOT_TOKEN`, `TELEGRAM_API`, `TELEGRAM_HASH`, `OWNER_ID`, `DATABASE_URL` |
| Port controls | `BASE_URL_PORT`, `RCLONE_SERVE_PORT` |
| License | [LICENSE](LICENSE) |

## Why Use It

WZML-X is built for users who want a single bot stack that can mirror, leech, manage files, and expose a simple web-based selection flow without stitching together multiple tools. The README focuses on what you need to deploy it quickly, understand the moving parts, and tune the behavior safely.

## What It Covers

| Capability | Outcome |
|---|---|
| Mirroring | Send files to Telegram with a controllable pipeline |
| Leeching | Deliver files in the format you prefer, including document and media workflows |
| File selection UI | Review and select torrent / NZB / upload contents before finalizing |
| Multi-source downloads | Use qBittorrent, Aria2, JDownloader, Mega, NZB, and yt-dlp integrations |
| Storage and upload paths | Push content to Google Drive, Rclone, Mega, and other supported routes |
| Automation | Limit tasks, tune queues, and manage startup updates from one config layer |

## How It Runs

Deploy with Docker and provide the required configuration values. The container takes care of the runtime path, so users only need to build or start the image and set their settings.

<details>
   <summary>What you need <kbd>Click Here</kbd></summary>

   - Docker installed
   - Your Telegram bot token and Telegram API credentials
   - A MongoDB connection string
   - The optional service credentials you want to enable, such as Drive, Rclone, Mega, JDownloader, or SABnzbd
</details>

## Deployment

<details open>
   <summary>Recommended: Docker Compose</summary>

   ```bash
   git clone https://github.com/SilentDemonSD/WZML-X.git
   cd WZML-X
   docker compose up --build
   ```

   Use this when you want the simplest full deployment path.
</details>

<details>
   <summary>Heroku Deployment</summary>

   1. **Create Heroku App**: Sign in to Heroku and create a new app.
   2. **Add Buildpacks**: Add `heroku/python` and `https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git`.
   3. **Set Config Vars**: Add all required variables from `config_sample.py` (e.g., `BOT_TOKEN`, `TELEGRAM_API`, etc.).
   4. **Connect GitHub**: Connect your repository to the Heroku app.
   5. **Deploy Branch**: Manual or automatic deploy from the main branch.
   6. **Start Dyno**: In the "Resources" tab, enable the `worker` dyno.

   *Note: Ensure your MongoDB is accessible from Heroku.*
</details>

<details>
   <summary>Single Container</summary>

   ```bash
   git clone https://github.com/SilentDemonSD/WZML-X.git
   cd WZML-X
   docker build -t wzmlx .
   docker run -p 80:80 -p 8080:8080 wzmlx
   ```

   Use this if you want a manual one-container deployment.
</details>

<details>
   <summary>Deployment Notes</summary>

   1. Set `BASE_URL_PORT` and `RCLONE_SERVE_PORT` to match the ports you want to expose.
   2. If you use qBittorrent, tune `AsyncIOThreadsCount` to your machine size.
   3. Stop the container before removing it, and remove the container before pruning images.
   4. Useful cleanup commands:

   ```bash
   sudo docker container prune
   sudo docker image prune -a
   ```
</details>

<details>
   <summary>Legacy Workflow Guide</summary>

   Some users still rely on the external workflow path referenced by the previous README:

   - [WZ Deploy workflow guide](https://github.com/SilentDemonSD/WZ-Deploy/tree/main?tab=readme-ov-file#2%EF%B8%8F%E2%83%A3-method-2-github-workflow-guide)

   Keep this only if that workflow still matches your deployment style.
</details>

## Configuration

Start with the required values:

- `BOT_TOKEN`
- `TELEGRAM_API`
- `TELEGRAM_HASH`
- `OWNER_ID`
- `DATABASE_URL`

Then tune the optional behavior from `config_sample.py`.

<details>
   <summary>Important user-facing settings</summary>

   | Setting | User impact |
   |---|---|
   | `DEFAULT_LANG` | Bot language |
   | `STATUS_LIMIT` | How much status data is shown |
   | `DEFAULT_UPLOAD` | Default upload target |
   | `LEECH_SPLIT_SIZE` | How large leech outputs are split |
   | `QUEUE_ALL`, `QUEUE_DOWNLOAD`, `QUEUE_UPLOAD` | Queue pressure and concurrency |
   | `SHOW_CLOUD_LINK` | Whether cloud links are shown to users |
   | `WEB_PINCODE` | Protects web access to file selection |
   | `UPDATE_PKGS` | Package refresh behavior during startup |
</details>

<details>
   <summary>Integrations available in config</summary>

   The sample config also covers:

   - qBittorrent and Aria2-related controls
   - JDownloader login details
   - Mega credentials
   - SABnzbd server definitions
   - Google Drive settings
   - RSS, search, media metadata, and logging controls
</details>

## Project Layout

| Path | Purpose |
|---|---|
| `bot/` | Bot core, handlers, listeners, and modules |
| `web/` | FastAPI app, templates, and the file selector UI |
| `gen_scripts/` | Setup helpers for sessions, tokens, and drive configuration |
| `plugins/` | Optional bot plugins |
| `qBittorrent/` | Default qBittorrent configuration |
| `sabnzbd/` | Default SABnzbd configuration |

## Documentation

> [!NOTE]
> This documentation is still being expanded.

- Full guides: `docs/`
- Deployment notes: the docs site linked from the repository at WZ Docs
- Configuration reference: `config_sample.py`

## Support

<details>
   <summary>Join Community</summary>

   - Telegram channel: https://t.me/WZML_X
   - Support group: https://t.me/WZML_Support
</details>

## Credits

WZML-X is a fork of [mirror-leech-telegram-bot](https://github.com/anasty17/mirror-leech-telegram-bot). The base project belongs to [anasty17](https://github.com/anasty17) and upstream contributors.

<details>
   <summary>Bot Authors</summary>

   <table>
      <thead>
         <tr>
            <th>Avatar</th>
            <th>Name</th>
            <th>Role</th>
            <th>Profile</th>
         </tr>
      </thead>
      <tbody>
         <tr>
            <td><img src="https://avatars.githubusercontent.com/u/105407900?v=4" width="72" alt="SilentDemonSD"></td>
            <td>SilentDemonSD</td>
            <td>Author, UI design, and custom features</td>
            <td><a href="https://github.com/SilentDemonSD">GitHub</a></td>
         </tr>
         <tr>
            <td><img src="https://avatars.githubusercontent.com/u/93116400?v=4" width="72" alt="RjRiajul"></td>
            <td>RjRiajul</td>
            <td>Co-author and maintainer</td>
            <td><a href="https://github.com/rjriajul">GitHub</a></td>
         </tr>
         <tr>
            <td><img src="https://avatars.githubusercontent.com/u/113664541?v=4" width="72" alt="CodeWithWeeb"></td>
            <td>CodeWithWeeb</td>
            <td>Feature expansion and wrap-up improvements</td>
            <td><a href="https://github.com/weebzone">GitHub</a></td>
         </tr>
         <tr>
            <td><img src="https://avatars.githubusercontent.com/u/84721324?v=4" width="72" alt="Maverick"></td>
            <td>Maverick</td>
            <td>Co-author and bug testing</td>
            <td><a href="https://github.com/MajnuRangeela">GitHub</a></td>
         </tr>
      </tbody>
   </table>
</details>

## License

This project is distributed under the terms of the repository license. See [LICENSE](LICENSE) for the full text.

