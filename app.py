"""AI-Based Mental Health Emotion Analyzer - Flask application.

Run with:  python app.py   ->  http://127.0.0.1:5000
Educational project. NOT a medical or psychological diagnosis tool.
"""
import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import Config
from database.db import db, init_db
from routes.auth_routes import auth_bp, get_current_user
from routes.analysis_routes import analysis_bp
from routes.dashboard_routes import dashboard_bp
from services.recommendation_engine import DISPLAY_NAMES
from services.speech_analyzer import SpeechAnalyzer
from services.text_analyzer import TextAnalyzer
from utils.errors import json_error

DISCLAIMER = ("This application is an educational AI-based emotional support tool. It does not provide "
              "medical or psychological diagnosis. If you are concerned about your mental health, consider "
              "speaking with a qualified professional or a trusted person.")

_FRIENDLY = {400: "The request was not valid.", 401: "Please log in to continue.", 403: "You are not allowed to do that.",
             404: "That page or resource was not found.", 405: "That action is not allowed here.",
             413: "The uploaded file is too large (maximum 16 MB).", 415: "Unsupported file type.",
             429: "Too many requests. Please wait and try again.", 500: "Something went wrong on our side."}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    if not app.config.get("TESTING") and (not app.config.get("SECRET_KEY_FROM_ENV")
                                          or app.config["SECRET_KEY"] == "change-this-secret-key"):
        print("[security] WARNING: set a strong SECRET_KEY in your .env file (see .env.example).")

    init_db(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)

    # AI services: models are loaded ONCE here, not per request.
    text_analyzer = TextAnalyzer(app.config)
    speech_analyzer = SpeechAnalyzer(app.config, text_analyzer)
    app.extensions["text_analyzer"] = text_analyzer
    app.extensions["speech_analyzer"] = speech_analyzer
    if app.config["LOAD_MODELS_ON_START"]:
        text_analyzer.load()
        speech_analyzer.load()

    app.register_blueprint(auth_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(dashboard_bp)

    @app.before_request
    def require_ajax_header():
        """Lightweight CSRF defence: state-changing API calls must come from our own JavaScript."""
        if (request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE")
                and request.headers.get("X-Requested-With") != "XMLHttpRequest"):
            return json_error(403, "Missing required request header.", "csrf_blocked")

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_globals():
        return {"current_user": get_current_user(), "disclaimer": DISCLAIMER, "emotion_names": DISPLAY_NAMES,
                "demo_mode": text_analyzer.using_demo}

    @app.errorhandler(Exception)
    def handle_error(error):
        """Friendly errors only - Python stack traces are never shown to users."""
        if isinstance(error, HTTPException):
            status, message = error.code or 500, _FRIENDLY.get(error.code or 500, error.description)
        else:
            status, message = 500, _FRIENDLY[500]
            db.session.rollback()
            app.logger.error("Unhandled %s", type(error).__name__)  # type only: no user content is logged
        if request.path.startswith("/api/"):
            return json_error(status, message, "http_error")
        return render_template("error.html", status=status, message=message), status

    @app.cli.command("seed-demo")
    def seed_demo():
        """Development only: create demo@example.com with 12 real analyses of sample sentences."""
        import json
        import random
        from datetime import timedelta

        from database.models import EmotionAnalysis, User, utcnow
        from routes.analysis_routes import SAMPLE_SENTENCES
        from services.recommendation_engine import recommendation_text

        user = User.query.filter_by(email="demo@example.com").first()
        if user is None:
            user = User(name="Demo User", email="demo@example.com")
            user.set_password("Demo@1234")
            db.session.add(user)
            db.session.commit()
        extra = ["I can't sleep because I keep worrying about tomorrow.", "Today was an ordinary day.",
                 "I feel lonely and low lately.", "I am so scared about the results."]
        for i in range(12):
            result = text_analyzer.analyze(random.choice(SAMPLE_SENTENCES + extra))
            db.session.add(EmotionAnalysis(
                user_id=user.id, input_type="text", emotion=result["emotion"],
                confidence=result["confidence"], emotion_scores=json.dumps(result["scores"]),
                recommendation=recommendation_text(result["emotion"]), is_demo=result["demo"],
                created_at=utcnow() - timedelta(days=random.randint(0, 6), hours=random.randint(0, 12))))
        db.session.commit()
        print("Demo user ready: demo@example.com / Demo@1234 (development only)")

    return app


if __name__ == "__main__":
    app = create_app()
    print("\n  Open http://127.0.0.1:5000 in your browser\n")
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"], use_reloader=False)
