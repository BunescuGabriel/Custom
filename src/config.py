from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"
LOG_DIR = BASE_DIR / "logs"
DATABASE_PATH = BASE_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
TTS_TIMEOUT_SECONDS = 180

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
