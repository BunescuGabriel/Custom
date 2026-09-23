from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
DATA_DIR = MEDIA_DIR / "data"
AUDIO_DIR = MEDIA_DIR / "audio"
BACKGROUND_DIR = MEDIA_DIR / "backgrounds"
VIDEO_DIR = MEDIA_DIR / "videos"
SUBTITLE_DIR = VIDEO_DIR / "subtitles"
TITLE_OVERLAY_DIR = VIDEO_DIR / "title_overlays"
LOG_DIR = DATA_DIR
DATABASE_PATH = DATA_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
TTS_TIMEOUT_SECONDS = 180
TTS_MAX_ATTEMPTS = 10
TTS_RETRY_DELAY_SECONDS = 1
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_TITLE_DURATION_SECONDS = 0.05
VIDEO_TITLE_PREVIEW_SECONDS = 1
VIDEO_TITLE_FONT_PATH = Path("C:/Windows/Fonts/arialbd.ttf")
VIDEO_TITLE_FONT_SIZE = 62
VIDEO_TITLE_MIN_FONT_SIZE = 24
VIDEO_TITLE_MAX_LINES = 4
VIDEO_TITLE_MAX_TEXT_WIDTH = 760
VIDEO_RENDER_TIMEOUT_SECONDS = 900

AUDIO_PROFILES = {
    "story": {
        "label": "Story",
        "rate_percent": -5,
        "pitch_hz": 0,
        "voice_by_language": {
            "Romana": "Emil",
            "Rusa": "Dmitry",
            "Engleza": "Guy",
            "Franceza": "Henri",
            "Germana": "Conrad",
            "Italiana": "Diego",
            "Spaniola": "Alvaro",
        },
    },
    "dialogue": {
        "label": "Dialogue",
        "rate_percent": -5,
        "pitch_hz": 0,
        "voice_by_language": {
            "Romana": "Alina",
            "Rusa": "Svetlana",
            "Engleza": "Jenny",
            "Franceza": "Denise",
            "Germana": "Katja",
            "Italiana": "Elsa",
            "Spaniola": "Elvira",
        },
    },
    "informative": {
        "label": "Informative",
        "rate_percent": 0,
        "pitch_hz": 0,
        "voice_by_language": {
            "Romana": "Alina",
            "Rusa": "Svetlana",
            "Engleza": "Jenny",
            "Franceza": "Denise",
            "Germana": "Katja",
            "Italiana": "Elsa",
            "Spaniola": "Elvira",
        },
    },
    "short_message": {
        "label": "Short message",
        "rate_percent": 2,
        "pitch_hz": 0,
        "voice_by_language": {
            "Romana": "Alina",
            "Rusa": "Svetlana",
            "Engleza": "Jenny",
            "Franceza": "Denise",
            "Germana": "Katja",
            "Italiana": "Elsa",
            "Spaniola": "Elvira",
        },
    },
}

VOICE_OPTIONS = {
    "Romana": {
        "Alina": "ro-RO-AlinaNeural",
        "Emil": "ro-RO-EmilNeural",
    },
    "Rusa": {
        "Svetlana": "ru-RU-SvetlanaNeural",
        "Dmitry": "ru-RU-DmitryNeural",
    },
    "Engleza": {
        "Jenny": "en-US-JennyNeural",
        "Guy": "en-US-GuyNeural",
    },
    "Franceza": {
        "Denise": "fr-FR-DeniseNeural",
        "Henri": "fr-FR-HenriNeural",
    },
    "Germana": {
        "Katja": "de-DE-KatjaNeural",
        "Conrad": "de-DE-ConradNeural",
    },
    "Italiana": {
        "Elsa": "it-IT-ElsaNeural",
        "Diego": "it-IT-DiegoNeural",
    },
    "Spaniola": {
        "Elvira": "es-ES-ElviraNeural",
        "Alvaro": "es-ES-AlvaroNeural",
    },
}
