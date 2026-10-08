"""Text and speech analysis: pages + API endpoints."""
import json
import os

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from database.models import EmotionAnalysis
from routes.auth_routes import get_current_user, login_required
from services import recommendation_engine as rec
from services.privacy_service import SUPPORT_NOTICE, safe_delete, save_temp_upload
from services.speech_analyzer import has_valid_signature
from utils.errors import AnalysisError, json_error

analysis_bp = Blueprint("analysis", __name__)

SAMPLE_SENTENCES = [  # demo examples only - they do not prove anything about a person
    "I feel happy today because I completed my project.",
    "I am worried about my upcoming examination.",
    "I have been feeling stressed because of too much work.",
    "I am angry about what happened today.",
]


def _save_and_respond(user, input_type, result, status_extra=None):
    """Create recommendation + insight, store ONLY the result, and build the JSON reply."""
    emotion, confidence, scores = result["emotion"], result["confidence"], result["scores"]
    recommendation = rec.get_recommendation(emotion)
    insight = rec.generate_insight(emotion, confidence, scores, input_type, result["demo"])

    record = EmotionAnalysis(
        user_id=user.id, input_type=input_type, emotion=emotion, confidence=confidence,
        emotion_scores=json.dumps({k: round(v, 4) for k, v in scores.items()}),
        recommendation=rec.recommendation_text(emotion), is_demo=result["demo"],
        audio_duration=result.get("duration"),
    )
    try:
        db.session.add(record)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return json_error(500, "Your result could not be saved. Please try again.", "database_error")

    history = (EmotionAnalysis.query.filter_by(user_id=user.id)
               .order_by(EmotionAnalysis.created_at.desc()).limit(10).all())
    body = {
        "id": record.id,
        "input_type": input_type,
        "emotion": emotion,
        "emotion_label": rec.DISPLAY_NAMES[emotion],
        "confidence": round(confidence * 100, 1),
        "scores": {k: round(v * 100, 1) for k, v in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)},
        "insight": insight,
        "recommendation": recommendation,
        "demo": result["demo"],
        "model": result["model"],
        "alert": rec.early_support_alert(history),
        "support_notice": SUPPORT_NOTICE if result.get("crisis") else None,
        "created_at": record.created_at.isoformat() + "Z",
    }
    if input_type == "speech":
        body.update({"duration": result["duration"], "features": result["features"],
                     "transcript_used": result["transcript_used"]})
    return jsonify(body), 200


# ---------------------------------------------------------------- pages
@analysis_bp.get("/analyze/text")
@login_required
def text_page():
    return render_template("text_analysis.html", samples=SAMPLE_SENTENCES,
                           max_length=current_app.config["MAX_TEXT_LENGTH"])


@analysis_bp.get("/analyze/speech")
@login_required
def speech_page():
    return render_template("speech_analysis.html",
                           allowed=sorted(current_app.config["ALLOWED_AUDIO_EXTENSIONS"]),
                           max_seconds=current_app.config["MAX_AUDIO_SECONDS"])


# ---------------------------------------------------------------- API
@analysis_bp.post("/api/analyze/text")
@login_required
def api_analyze_text():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "text" not in data:
        return json_error(400, "Invalid request. Please send JSON with a 'text' field.", "invalid_request")
    try:
        result = current_app.extensions["text_analyzer"].analyze(data["text"])
    except AnalysisError as exc:
        return json_error(exc.status, exc.message, exc.code)
    return _save_and_respond(get_current_user(), "text", result)


@analysis_bp.post("/api/analyze/speech")
@login_required
def api_analyze_speech():
    cfg = current_app.config
    upload = request.files.get("audio")
    if upload is None or not upload.filename:
        return json_error(400, "Please choose or record an audio file first.", "no_audio")
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in cfg["ALLOWED_AUDIO_EXTENSIONS"]:
        allowed = ", ".join(sorted(cfg["ALLOWED_AUDIO_EXTENSIONS"])).upper()
        return json_error(415, f"Unsupported audio format. Please use: {allowed}.", "unsupported_format")

    use_transcript = request.form.get("use_transcript", "false").lower() == "true"
    path = None
    try:
        path = save_temp_upload(upload, cfg["UPLOAD_FOLDER"], extension)
        if not has_valid_signature(path, extension):
            return json_error(415, "This file does not look like a valid audio file.", "invalid_audio")
        result = current_app.extensions["speech_analyzer"].analyze(path, use_transcript=use_transcript)
    except AnalysisError as exc:
        return json_error(exc.status, exc.message, exc.code)
    except OSError:
        return json_error(500, "The uploaded file could not be processed.", "upload_error")
    finally:
        safe_delete(path)  # raw audio is never kept
    return _save_and_respond(get_current_user(), "speech", result)
