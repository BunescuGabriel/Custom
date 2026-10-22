# Text to Audio and Video

Local MP3 and vertical MP4 generation with cached audio, captions, and local
history. It requires Python **3.13** on Windows or Linux. macOS also needs a
compatible font for MP4 title rendering.

## Install and run

In PowerShell, from the project directory:

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm --prefix src/frontend install
```

Double-click `start-react-fastapi.cmd` to start FastAPI and React in separate
terminals. Alternatively, use two terminals:

```powershell
.venv/Scripts/python.exe -m src.api_main
npm --prefix src/frontend run dev
```

Open the Vite address, normally `http://127.0.0.1:5173`. FastAPI listens only
on `127.0.0.1:8000`; the development frontend proxies `/api` requests to it.
Build the frontend for production with:

```powershell
npm --prefix src/frontend run build
```

## Configuration and Docker

`.env` holds local or sensitive values and is ignored by Git. Copy
`.env.example` when setting up a new machine. Public application defaults,
limits, voice options, and video defaults are stored in `config/settings.json`.

With Docker Desktop installed, start both services with:

```powershell
docker compose up --build
```

React is available on `http://127.0.0.1:5173` and FastAPI on
`http://127.0.0.1:8000`. Generated media remains in the local `media` folder.

`requirements.txt` defines Python dependencies. `edge-tts==7.3.1` supports the
current Microsoft Edge TTS protocol and supplies the `WordBoundary` timing used
for captions. This application has a single local history without user accounts.
Do not expose it to an untrusted network.

## Generation and privacy

- New synthesis sends text to Microsoft Edge through `edge-tts`, so it needs
  internet access. Language detection runs locally and valid cache entries can
  be reused without a new request.
- Romanian, Russian, English, French, German, Italian, and Spanish are
  available. Detection is an estimate; review short, mixed, or unsupported text.
- Limits are 12,000 characters, about 10 minutes of narration, and a 100 MB,
  4K, 10-minute background. Final audio duration is validated separately.
- Only one expensive generation runs in the same storage directory at a time,
  including across processes.
- Jobs and their settings are stored before processing. The React interface
  polls job status, and completed audio/video is playable directly in the app.
- Cancelling stops synthesis or FFmpeg and retains media that has completed.

Text, settings, and media stay on disk until deleted. Logs rotate at 10 MiB and
keep up to 100 copies. Use `LOG_LEVEL` for verbosity, `LOG_FORMAT=json` for
JSON-only console output, and `NO_COLOR` to disable console colors.

## Vertical MP4

Install FFmpeg and FFprobe with `libass`, `libx264`, and AAC in `PATH`. Use an
[official FFmpeg distribution](https://ffmpeg.org/download.html). On Ubuntu:

```sh
sudo apt-get install ffmpeg fonts-dejavu-core
```

Output is 1080 × 1920 at 30 FPS with H.264/AAC. The source background audio is
removed. You can select left, center, or right cropping. The optional intro is
0–10 seconds (0.5 seconds by default); captions shift by the same duration.

Title fonts use Arial Bold on Windows/macOS and DejaVu/Liberation Sans on Linux.
Set `VIDEO_TITLE_FONT_PATH` to a suitable TTF when additional characters are
needed. Missing codecs and fonts are detected before synthesis.

## Storage

- `media/data/app.db`: persistent history and job state.
- `media/data/app.log`: diagnostics and UTC timestamps.
- `media/audio`: MP3 files and JSONL metadata.
- `media/backgrounds`: uploaded video backgrounds.
- `media/videos`: MP4 files, subtitle files, and temporary files.

For backup or relocation, stop the application and copy the entire `media`
directory. Set `APP_MEDIA_DIR` to use a different location.

## Development

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m black --check .
.venv/Scripts/python.exe -m pytest -q
npm --prefix src/frontend run build
```

FFmpeg and FFprobe are required for tests marked `integration` and for real
audio/video generation. Run unit tests only with:

```powershell
.venv/Scripts/python.exe -m pytest -m "not integration"
```
