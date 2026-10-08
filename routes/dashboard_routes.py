"""Public pages, dashboard, history, recommendations and health check."""
from collections import Counter
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from database.models import EmotionAnalysis, utcnow
from routes.auth_routes import get_current_user, login_required
from services import recommendation_engine as rec
from services import privacy_service
from utils.errors import json_error

dashboard_bp = Blueprint("dashboard", __name__)


# ---------------------------------------------------------------- pages
@dashboard_bp.get("/")
def index():
    return render_template("index.html")


@dashboard_bp.get("/about")
def about():
    return render_template("about.html")


@dashboard_bp.get("/privacy")
def privacy():
    return render_template("privacy.html", collected=privacy_service.DATA_COLLECTED,
                           not_collected=privacy_service.DATA_NOT_COLLECTED)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html")


@dashboard_bp.get("/history")
@login_required
def history_page():
    return render_template("history.html", emotions=rec.EMOTIONS, names=rec.DISPLAY_NAMES)


@dashboard_bp.get("/recommendations")
def recommendations_page():
    return render_template("recommendations.html")


# ---------------------------------------------------------------- API
@dashboard_bp.get("/api/health")
def api_health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "error"
    text_status = current_app.extensions["text_analyzer"].status()
    speech_status = current_app.extensions["speech_analyzer"].status()
    return jsonify({"status": "ok" if database == "ok" else "degraded", "database": database,
                    "text_model": text_status, "speech_model": speech_status})


@dashboard_bp.get("/api/dashboard")
@login_required
def api_dashboard():
    user = get_current_user()
    try:
        tz_offset = max(-840, min(840, int(request.args.get("tz_offset", 0))))
    except ValueError:
        tz_offset = 0

    rows = (EmotionAnalysis.query.filter_by(user_id=user.id)
            .order_by(EmotionAnalysis.created_at.desc()).all())

    distribution = Counter(r.emotion for r in rows)
    types = Counter(r.input_type for r in rows)
    scores = [rec.wellbeing_score(r.scores) for r in rows]

    # Weekly trend: last 7 days in the user's local time (tz_offset = JS getTimezoneOffset)
    today = (utcnow() - timedelta(minutes=tz_offset)).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    buckets = {d: [] for d in days}
    for r in rows:
        local_day = (r.created_at - timedelta(minutes=tz_offset)).date()
        if local_day in buckets:
            buckets[local_day].append(r.scores)
    weekly = {
        "labels": [d.strftime("%a %d %b") for d in days],
        "wellbeing": [round(sum(rec.wellbeing_score(s) for s in buckets[d]) / len(buckets[d]), 1) if buckets[d] else None for d in days],
        "negative": [round(100 * sum(rec.negative_load(s) for s in buckets[d]) / len(buckets[d]), 1) if buckets[d] else None for d in days],
        "counts": [len(buckets[d]) for d in days],
    }

    latest = rows[0] if rows else None
    return jsonify({
        "user": {"name": user.name},
        "total": len(rows),
        "latest": {"emotion": latest.emotion, "confidence": round(latest.confidence * 100, 1),
                   "created_at": latest.created_at.isoformat() + "Z"} if latest else None,
        "most_frequent": distribution.most_common(1)[0][0] if rows else None,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "distribution": {e: distribution.get(e, 0) for e in rec.EMOTIONS},
        "types": {"text": types.get("text", 0), "speech": types.get("speech", 0)},
        "weekly": weekly,
        "recent": [{"id": r.id, "created_at": r.created_at.isoformat() + "Z", "input_type": r.input_type,
                    "emotion": r.emotion, "confidence": round(r.confidence * 100, 1), "demo": bool(r.is_demo)}
                   for r in rows[:8]],
        "alert": rec.early_support_alert(rows),
    })


@dashboard_bp.get("/api/history")
@login_required
def api_history():
    user = get_current_user()
    query = EmotionAnalysis.query.filter_by(user_id=user.id)

    emotion = request.args.get("emotion", "").strip().lower()
    if emotion in rec.EMOTIONS:
        query = query.filter(EmotionAnalysis.emotion == emotion)
    input_type = request.args.get("type", "").strip().lower()
    if input_type in ("text", "speech"):
        query = query.filter(EmotionAnalysis.input_type == input_type)
    search = request.args.get("search", "").strip()[:60]
    if search:
        like = f"%{search}%"
        query = query.filter(or_(EmotionAnalysis.emotion.ilike(like), EmotionAnalysis.recommendation.ilike(like),
                                 EmotionAnalysis.input_type.ilike(like)))

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = max(1, min(50, int(request.args.get("per_page", 10))))
    except ValueError:
        page, per_page = 1, 10
    total = query.count()
    rows = (query.order_by(EmotionAnalysis.created_at.desc())
            .offset((page - 1) * per_page).limit(per_page).all())
    items = [{"id": r.id, "created_at": r.created_at.isoformat() + "Z", "input_type": r.input_type,
              "emotion": r.emotion, "confidence": round(r.confidence * 100, 1),
              "recommendation": r.recommendation, "demo": bool(r.is_demo)} for r in rows]
    return jsonify({"items": items, "total": total, "page": page, "per_page": per_page,
                    "pages": max(1, -(-total // per_page))})


@dashboard_bp.delete("/api/history/<int:analysis_id>")
@login_required
def api_delete_one(analysis_id):
    user = get_current_user()
    record = EmotionAnalysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    if record is None:
        return json_error(404, "That history item was not found.", "not_found")
    try:
        db.session.delete(record)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return json_error(500, "Could not delete the item. Please try again.", "database_error")
    return jsonify({"message": "History item deleted.", "id": analysis_id})


@dashboard_bp.delete("/api/history")
@login_required
def api_clear_history():
    try:
        deleted = privacy_service.delete_user_history(get_current_user().id)
    except SQLAlchemyError:
        db.session.rollback()
        return json_error(500, "Could not clear the history. Please try again.", "database_error")
    return jsonify({"message": "Your history was cleared.", "deleted": deleted})


@dashboard_bp.get("/api/recommendations")
def api_recommendations():
    user = get_current_user()
    latest_emotion = None
    if user:
        latest = (EmotionAnalysis.query.filter_by(user_id=user.id)
                  .order_by(EmotionAnalysis.created_at.desc()).first())
        latest_emotion = latest.emotion if latest else None
    return jsonify({"recommendations": rec.all_recommendations(), "latest_emotion": latest_emotion,
                    "disclaimer": rec.GENERAL_NOTE})
