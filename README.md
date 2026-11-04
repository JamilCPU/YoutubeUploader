# YouTube Uploader

Automatically uploads OBS recordings to YouTube when recording finishes. The app watches a folder for new video files, waits until a file stops changing, then uploads it to your channel as a private video titled with the date and time. It can run as a command-line process, with a small Windows tray GUI, or in a Windows container.

## Stack

- Python 3.7+
- `watchdog` for file system events
- Google API client libraries (YouTube Data API v3, OAuth 2.0 desktop flow)
- PySide6 for the optional GUI (Windows)
- Docker (Windows containers) via `Dockerfile` and `docker-compose.yml`

## Running

### 1. Google Cloud setup

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable **YouTube Data API v3**.
2. Create an **OAuth client ID** of type *Desktop app* and note the client ID and secret.
3. On the OAuth consent screen, add the scope `https://www.googleapis.com/auth/youtube.upload` and add yourself as a test user.

### 2. Install and configure

```bash
pip install -r requirements.txt
export YOUTUBE_CLIENT_ID='your-client-id'
export YOUTUBE_CLIENT_SECRET='your-client-secret'
export YOUTUBE_PROJECT_ID='your-project-id'   # optional
```

On Windows PowerShell use `$env:YOUTUBE_CLIENT_ID="..."` instead of `export`.

### 3. Start

```bash
python main.py          # command line
python main.py --gui    # windowed / tray mode
```

On first run a browser window opens for Google sign-in. The resulting token is saved to `token.json`, which is gitignored and reused afterwards. If authentication goes wrong, delete `token.json` and sign in again.

### Docker (Windows containers)

See [DOCKER.md](DOCKER.md). In short:

```powershell
.\validate-docker-setup.ps1   # optional prerequisite check
docker-compose up --build
```

Edit the bind-mounted recordings folder in `docker-compose.yml` to match your machine.

## How it works

1. `watchdog` notices a new file in the watched directory (the `WATCH_DIR` environment variable, otherwise `F:\Recordings` as coded in `main.py`).
2. The handler polls the file on an interval (60 seconds by default). If the file was modified since the last check it waits another interval; otherwise it treats the recording as finished.
3. The file is uploaded as a private video titled with the current date and time, and the status is logged. Change visibility later in YouTube Studio.

Only one file is tracked at a time. The GUI also remembers the last chosen directory in `config.json` (also gitignored).

## Configuration

- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` (required)
- `YOUTUBE_PROJECT_ID` (optional)
- `WATCH_DIR` - directory to watch
- `DATA_DIR` - where `config.json` and `token.json` are stored (defaults to the current directory)

## Project layout

- `main.py` - entry point; wires the watcher and uploader together
- `fileHandler.py` - detects finished recordings and triggers uploads
- `uploader.py` - OAuth and YouTube upload logic
- `gui.py` - PySide6 window and system tray icon
- `config.py` - persists the chosen directory
- `watcher.py` - file watching helper
