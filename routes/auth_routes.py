"""Registration, login, logout + the login/register pages."""
import re
import time
from functools import wraps

from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from database.models import User
from services.privacy_service import delete_account
from utils.errors import json_error

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FAILED_LOGINS = {}  # (ip, email) -> [timestamps]; simple brute-force protection
_MAX_FAILS, _WINDOW = 8, 300


def get_current_user():
    """Return the logged-in User (or None). Cached per request."""
    if "user" in g:
        return g.user
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if user_id and user is None:
        session.clear()
    g.user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            if request.path.startswith("/api/"):
                return json_error(401, "Please log in to continue.", "unauthorized")
            return redirect(url_for("auth.login_page", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _validate_password(password: str):
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 128:
        return "Password is too long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def _too_many_failures(key) -> bool:
    now = time.time()
    attempts = [t for t in _FAILED_LOGINS.get(key, []) if now - t < _WINDOW]
    _FAILED_LOGINS[key] = attempts
    return len(attempts) >= _MAX_FAILS


# ---------------------------------------------------------------- pages
@auth_bp.get("/login")
def login_page():
    if get_current_user():
        return redirect(url_for("dashboard.dashboard_page"))
    return render_template("login.html")


@auth_bp.get("/register")
def register_page():
    if get_current_user():
        return redirect(url_for("dashboard.dashboard_page"))
    return render_template("register.html")


# ---------------------------------------------------------------- API
@auth_bp.post("/api/register")
def api_register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error(400, "Invalid request. Please send JSON.", "invalid_request")
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not 2 <= len(name) <= 80:
        return json_error(400, "Please enter your name (2-80 characters).", "invalid_name")
    if len(email) > 255 or not EMAIL_RE.match(email):
        return json_error(400, "Please enter a valid e-mail address.", "invalid_email")
    problem = _validate_password(password)
    if problem:
        return json_error(400, problem, "weak_password")
    if User.query.filter_by(email=email).first():
        return json_error(409, "An account with this e-mail already exists.", "email_taken")

    user = User(name=name, email=email)
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return json_error(500, "Could not create the account. Please try again.", "database_error")

    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify({"message": "Account created.", "user": {"id": user.id, "name": user.name, "email": user.email}}), 201


@auth_bp.post("/api/login")
def api_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error(400, "Invalid request. Please send JSON.", "invalid_request")
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    key = (request.remote_addr, email)

    if _too_many_failures(key):
        return json_error(429, "Too many failed attempts. Please wait a few minutes and try again.", "too_many_attempts")
    user = User.query.filter_by(email=email).first() if email else None
    if user is None or not isinstance(password, str) or not user.check_password(password):
        _FAILED_LOGINS.setdefault(key, []).append(time.time())
        return json_error(401, "Incorrect e-mail or password.", "invalid_credentials")

    _FAILED_LOGINS.pop(key, None)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify({"message": "Logged in.", "user": {"id": user.id, "name": user.name, "email": user.email}})


@auth_bp.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@auth_bp.delete("/api/account")
@login_required
def api_delete_account():
    """Delete the account and all its data (the password must be confirmed)."""
    data = request.get_json(silent=True) or {}
    user = get_current_user()
    if not user.check_password(str(data.get("password", ""))):
        return json_error(403, "Password is incorrect.", "invalid_credentials")
    try:
        delete_account(user)
    except SQLAlchemyError:
        db.session.rollback()
        return json_error(500, "Could not delete the account. Please try again.", "database_error")
    session.clear()
    return jsonify({"message": "Your account and all stored results were deleted."})
