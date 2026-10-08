import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from database.db import db  # noqa: E402

AJAX = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    c = app.test_client()
    c.environ_base["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
    return c


@pytest.fixture()
def auth_client(client):
    res = client.post("/api/register", json={"name": "Test User", "email": "test@example.com", "password": "Passw0rd123"})
    assert res.status_code == 201
    return client
