"""SQLAlchemy setup (Flask-SQLAlchemy)."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Bind SQLAlchemy to the app and create the tables if they do not exist."""
    db.init_app(app)
    with app.app_context():
        from database import models  # noqa: F401  (registers the tables)
        db.create_all()
