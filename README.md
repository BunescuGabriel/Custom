# Text to Audio

Run the application with `python main.py` from the project's virtual environment.

## Local files

- `media/data/app.db`: SQLite database containing generation history.
- `media/data/app.log`: application logs, rotated at 10 MiB with up to 100 backups.
- `media/audio/`: generated audio files referenced by the database.
- `media/backgrounds/`: local copies of the video backgrounds selected for MP4.
- `media/videos/`: generated vertical MP4 files, subtitles, and temporary title overlays.

The `media` directory is created automatically and excluded from Git. Paths are
resolved relative to the project, independently of the working directory.

At startup, `python main.py` initializes storage before launching Streamlit,
without waiting for the browser to open:

- If `media/data/` is missing, it creates the directory and `media/data/app.db`.
- If `media/data/` exists but `app.db` is missing, it creates the database inside it.
- If both exist, it reuses the database and preserves the existing history.

Alembic automatically creates or updates the required database tables.

## Logging

Application modules use `logging.getLogger(__name__)` and inherit the `src`
logger's configuration. Startup migrations preserve that configuration.
Timestamps use UTC; exceptions include their traceback. Console output is colored
when attached to a terminal; log files contain plain UTF-8 text.

- `LOG_LEVEL`: logging level, default `INFO`; for example `DEBUG` or `WARNING`.
- `LOG_FORMAT=json`: emit one JSON object per console record, with no file logging,
  matching the reference bot's behavior for container log collection.
- `NO_COLOR`: disable console colors when this environment variable is present.

Repeated Streamlit runs reuse the handlers without duplicating log messages.
Database migrations can also be run with `alembic upgrade head`.

## MP4 pentru TikTok

Selecteaza `MP4` in Generator, incarca un videoclip de fundal pe care ai dreptul
sa-l folosesti, iar aplicatia pastreaza MP3-ul generat si creeaza un MP4 vertical
de 1080 × 1920. Audio-ul fundalului este eliminat; videoclipul foloseste numai
naratiunea generata si subtitrari arse in imagine.

Titlul ales in Generator este randat ca o caseta PNG dinamica, dimensionata dupa
text, cu fundal negru si accente turcoaz/rosii. Este afisata doar la inceputul
MP4-ului, apoi dispare brusc, iar subtitrarile naratiunii continua imediat.

In timpul afisarii titlului, fundalul este cadrul de la secunda `1` al
videoclipului. Dupa disparitia titlului, fundalul principal incepe normal de la
secunda `0`.

Pentru MP4 trebuie instalate `ffmpeg` si `ffprobe`, iar ambele comenzi trebuie sa
fie disponibile in `PATH`. Dupa instalare, inchide si redeschide terminalul, apoi
porneste din nou aplicatia. Daca fundalul este mai scurt decat naratiunea, acesta
este reluat automat pana la finalul audio-ului.
