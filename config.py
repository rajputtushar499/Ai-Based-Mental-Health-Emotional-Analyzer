"""Application configuration. Values are read from environment variables (.env file)."""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list) -> list:
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    # --- Security ---------------------------------------------------------
    # If SECRET_KEY is missing a random one is generated (sessions reset on restart).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    SECRET_KEY_FROM_ENV = bool(os.environ.get("SECRET_KEY"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    CORS_ORIGINS = _env_list("CORS_ORIGINS", ["http://127.0.0.1:5000", "http://localhost:5000"])

    # --- Database ---------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///mental_health.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Uploads ----------------------------------------------------------
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "flac", "ogg"}
    MAX_AUDIO_SECONDS = 60
    MIN_AUDIO_SECONDS = 1.0

    # --- Text analysis ----------------------------------------------------
    MAX_TEXT_LENGTH = 2000
    MIN_TEXT_LENGTH = 3

    # --- AI models --------------------------------------------------------
    TEXT_MODEL_ID = os.environ.get("TEXT_MODEL_ID", "bhadresh-savani/distilbert-base-uncased-emotion")
    SPEECH_BACKEND = os.environ.get("SPEECH_BACKEND", "huggingface")  # huggingface | sklearn
    SPEECH_MODEL_ID = os.environ.get("SPEECH_MODEL_ID", "superb/wav2vec2-base-superb-er")
    SPEECH_SKLEARN_MODEL_PATH = os.environ.get("SPEECH_SKLEARN_MODEL_PATH", str(BASE_DIR / "models" / "speech_clf.joblib"))
    DEMO_MODE = _env_bool("DEMO_MODE", False)
    ALLOW_DEMO_FALLBACK = _env_bool("ALLOW_DEMO_FALLBACK", True)
    LOAD_MODELS_ON_START = _env_bool("LOAD_MODELS_ON_START", True)

    DEBUG = _env_bool("FLASK_DEBUG", False)
    TESTING = False


class TestConfig(Config):
    """Used by the automated tests: in-memory database, no model downloads."""
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DEMO_MODE = True
    LOAD_MODELS_ON_START = False
