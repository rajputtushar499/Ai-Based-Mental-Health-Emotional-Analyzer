"""Database tables: User and EmotionAnalysis."""
import json
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite does not store time zones)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # One user -> many analyses. Deleting a user deletes their analyses too.
    analyses = db.relationship(
        "EmotionAnalysis", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)  # salted PBKDF2/scrypt hash

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class EmotionAnalysis(db.Model):
    """One analysis result. The raw text / audio is NEVER stored."""

    __tablename__ = "emotion_analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    input_type = db.Column(db.String(10), nullable=False)  # "text" | "speech"
    emotion = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.Float, nullable=False)  # 0..1
    emotion_scores = db.Column(db.Text, nullable=False)  # JSON: {"stress": 0.7, ...}
    recommendation = db.Column(db.Text, nullable=False, default="")
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    audio_duration = db.Column(db.Float, nullable=True)  # seconds, speech only
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="analyses")

    @property
    def scores(self) -> dict:
        try:
            return json.loads(self.emotion_scores)
        except (TypeError, ValueError):
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "input_type": self.input_type,
            "emotion": self.emotion,
            "confidence": round(self.confidence * 100, 1),
            "scores": {k: round(v * 100, 1) for k, v in self.scores.items()},
            "recommendation": self.recommendation,
            "demo": bool(self.is_demo),
            "audio_duration": self.audio_duration,
            "created_at": self.created_at.isoformat() + "Z",
        }
