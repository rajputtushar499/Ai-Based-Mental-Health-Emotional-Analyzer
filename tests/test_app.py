"""Home page, registration and login."""


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"AI-Based Mental Health Emotion Analyzer" in res.data
    assert b"does not provide" in res.data  # disclaimer visible


def test_public_pages_load(client):
    for path in ("/about", "/privacy", "/login", "/register", "/recommendations"):
        assert client.get(path).status_code == 200, path


def test_register_and_duplicate(client):
    body = {"name": "Asha", "email": "Asha@Example.com", "password": "Secret123"}
    assert client.post("/api/register", json=body).status_code == 201
    assert client.post("/api/register", json=body).status_code == 409


def test_register_validation(client):
    assert client.post("/api/register", json={"name": "A", "email": "bad", "password": "x"}).status_code == 400
    assert client.post("/api/register", json={"name": "Asha", "email": "a@b.com", "password": "short1"}).status_code == 400
    assert client.post("/api/register", data="not json").status_code == 400


def test_password_is_hashed(app, auth_client):
    from database.models import User

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        assert user.password_hash != "Passw0rd123"
        assert user.check_password("Passw0rd123")


def test_login_logout(client):
    client.post("/api/register", json={"name": "Ravi", "email": "ravi@example.com", "password": "Secret123"})
    client.post("/api/logout")
    assert client.get("/api/dashboard").status_code == 401
    assert client.post("/api/login", json={"email": "ravi@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"email": "ravi@example.com", "password": "Secret123"}).status_code == 200
    assert client.get("/api/dashboard").status_code == 200


def test_protected_page_redirects(client):
    res = client.get("/dashboard")
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_csrf_header_required(app):
    plain = app.test_client()  # no X-Requested-With header
    res = plain.post("/api/login", json={"email": "a@b.com", "password": "x"})
    assert res.status_code == 403


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200 and res.get_json()["database"] == "ok"
