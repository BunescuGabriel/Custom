# Text to Audio

Run the application with `python main.py` from the project's virtual environment.

## Local files

- `data/app.db`: SQLite database containing generation history.
- `data/app.log`: application logs, rotated at 10 MiB with up to 100 backups.
- `audio/`: generated audio files referenced by the database.

The `data` directory is created automatically and excluded from Git. Paths are
resolved relative to the project, independently of the working directory.

At startup, `python main.py` initializes storage before launching Streamlit,
without waiting for the browser to open:

- If `data/` is missing, it creates the directory and `data/app.db`.
- If `data/` exists but `app.db` is missing, it creates the database inside it.
- If both exist, it reuses the database and preserves the existing history.

Alembic automatically creates or updates the required database tables.

When updating an older installation, stop the application and move the existing
`app.db` into `data/app.db` before restarting to preserve its history. Do not
overwrite an existing destination database. Move `logs/app.log*` into `data/`
to retain previous logs as well.

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
