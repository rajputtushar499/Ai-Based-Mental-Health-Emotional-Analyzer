"""Privacy helpers: temp-file handling, crisis-language check, data deletion."""
import os
import re
import uuid

from werkzeug.utils import secure_filename

from database.db import db
from database.models import EmotionAnalysis

# Phrases that may indicate someone is in serious distress. The text is only checked in
# memory - the result is a boolean that is shown to the user and is NOT stored.
_CRISIS_PATTERNS = [
    r"\bkill (myself|me)\b", r"\bend (my|it all|my own) life\b", r"\bwant(ed)? to die\b",
    r"\bsuicid", r"\bself[- ]?harm", r"\b(hurt|harm|cut)(ting)? myself\b",
    r"\bno reason to (live|go on)\b", r"\bbetter off (dead|without me)\b",
    r"\bcan'?t (go on|do this anymore)\b", r"\bdon'?t want to (live|be alive|exist)\b",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)

SUPPORT_NOTICE = (
    "Some of the words you used suggest you may be going through something very painful. "
    "You do not have to handle this alone. Please consider talking with a trusted person "
    "or a qualified mental-health professional right now. If you may be in immediate danger, "
    "contact your local emergency number. In India you can call Tele-MANAS at 14416 "
    "(free, 24x7); elsewhere, search for your country's crisis helpline."
)


def contains_crisis_language(text: str) -> bool:
    return bool(_CRISIS_RE.search(text or ""))


# --- temporary upload handling ------------------------------------------------------
def save_temp_upload(file_storage, folder: str, extension: str) -> str:
    """Save an upload under a random name and return the path (caller must delete it)."""
    os.makedirs(folder, exist_ok=True)
    safe = secure_filename(file_storage.filename or "audio") or "audio"
    stem = os.path.splitext(safe)[0][:30] or "audio"
    path = os.path.join(folder, f"{uuid.uuid4().hex}_{stem}.{extension}")
    file_storage.save(path)
    return path


def safe_delete(path) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass  # nothing sensitive is logged; a leftover temp file is harmless


# --- data deletion -------------------------------------------------------------------
def delete_user_history(user_id: int) -> int:
    count = EmotionAnalysis.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return count


def delete_account(user) -> None:
    db.session.delete(user)  # cascades to the user's analyses
    db.session.commit()


# --- what the Privacy page explains ----------------------------------------------------
DATA_COLLECTED = [
    {"item": "Name, e-mail, password hash", "why": "To create your account and sign you in. The password is never stored - only a salted hash."},
    {"item": "Analysis results", "why": "Detected emotion, confidence, probabilities and the wellness tips shown, so that the dashboard and history can work."},
    {"item": "Input type and time", "why": "To show text vs speech counts and weekly trends."},
]
DATA_NOT_COLLECTED = [
    "The text you type is analysed in memory and is not saved.",
    "Uploaded or recorded audio is deleted from the server immediately after analysis.",
    "No analysis content is written to the server logs.",
]
