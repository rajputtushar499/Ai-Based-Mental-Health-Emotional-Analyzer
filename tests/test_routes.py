"""Analysis, dashboard, history and deletion endpoints."""
SENTENCES = ["I feel happy today because I completed my project.", "I am worried about my upcoming examination.",
             "I have been feeling stressed because of too much work.", "I am angry about what happened today."]


def analyze(client, text):
    return client.post("/api/analyze/text", json={"text": text})


def test_analysis_requires_login(client):
    assert analyze(client, "hello there").status_code == 401


def test_text_analysis(auth_client):
    res = analyze(auth_client, SENTENCES[1])
    assert res.status_code == 200
    data = res.get_json()
    for key in ("emotion", "confidence", "scores", "insight", "recommendation", "demo"):
        assert key in data
    assert data["demo"] is True
    assert "diagnos" in data["insight"].lower()


def test_invalid_text_inputs(auth_client):
    assert analyze(auth_client, "").status_code == 400
    assert analyze(auth_client, "x" * 5000).status_code == 400
    assert auth_client.post("/api/analyze/text", json={"nope": 1}).status_code == 400
    assert auth_client.post("/api/analyze/text", json={"text": 42}).status_code == 400


def test_raw_text_not_stored(app, auth_client):
    from database.models import EmotionAnalysis

    analyze(auth_client, "my very private sentence about exams")
    with app.app_context():
        row = EmotionAnalysis.query.first()
        blob = " ".join(str(getattr(row, c.name)) for c in row.__table__.columns)
        assert "private" not in blob


def test_crisis_language_shows_support_notice(auth_client):
    data = analyze(auth_client, "I want to die and I feel hopeless").get_json()
    assert data["support_notice"]


def test_dashboard_api(auth_client):
    for s in SENTENCES:
        analyze(auth_client, s)
    data = auth_client.get("/api/dashboard?tz_offset=-330").get_json()
    assert data["total"] == 4 and data["types"]["text"] == 4
    assert data["latest"] and len(data["recent"]) == 4
    assert sum(data["distribution"].values()) == 4
    assert len(data["weekly"]["labels"]) == 7


def test_history_filter_search_and_delete(auth_client):
    for s in SENTENCES:
        analyze(auth_client, s)
    hist = auth_client.get("/api/history").get_json()
    assert hist["total"] == 4
    assert auth_client.get("/api/history?type=speech").get_json()["total"] == 0
    emotion = hist["items"][0]["emotion"]
    assert auth_client.get(f"/api/history?emotion={emotion}").get_json()["total"] >= 1

    first = hist["items"][0]["id"]
    assert auth_client.delete(f"/api/history/{first}").status_code == 200
    assert auth_client.delete(f"/api/history/{first}").status_code == 404
    assert auth_client.get("/api/history").get_json()["total"] == 3
    assert auth_client.delete("/api/history").status_code == 200
    assert auth_client.get("/api/history").get_json()["total"] == 0


def test_users_cannot_see_each_others_history(app, auth_client):
    analyze(auth_client, SENTENCES[0])
    item_id = auth_client.get("/api/history").get_json()["items"][0]["id"]
    other = app.test_client()
    other.environ_base["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
    other.post("/api/register", json={"name": "Other", "email": "o@example.com", "password": "Secret123"})
    assert other.get("/api/history").get_json()["total"] == 0
    assert other.delete(f"/api/history/{item_id}").status_code == 404


def test_recommendations_api(client):
    data = client.get("/api/recommendations").get_json()
    assert len(data["recommendations"]) == 7


def test_early_support_alert(auth_client):
    for _ in range(4):
        data = analyze(auth_client, "I am so stressed and worried, overwhelmed by pressure").get_json()
    assert data["alert"] is not None
    assert "difficult period" in data["alert"]["message"]


def test_speech_validation(auth_client):
    import io

    assert auth_client.post("/api/analyze/speech").status_code == 400
    bad_ext = {"audio": (io.BytesIO(b"hello"), "notes.txt")}
    assert auth_client.post("/api/analyze/speech", data=bad_ext, content_type="multipart/form-data").status_code == 415
    fake = {"audio": (io.BytesIO(b"this is not audio at all"), "fake.wav")}
    assert auth_client.post("/api/analyze/speech", data=fake, content_type="multipart/form-data").status_code == 415


def test_delete_account(auth_client):
    assert auth_client.delete("/api/account", json={"password": "wrong"}).status_code == 403
    assert auth_client.delete("/api/account", json={"password": "Passw0rd123"}).status_code == 200
    assert auth_client.get("/api/dashboard").status_code == 401


def test_unknown_api_route_is_json(client):
    res = client.get("/api/nope")
    assert res.status_code == 404 and res.get_json()["error"]
