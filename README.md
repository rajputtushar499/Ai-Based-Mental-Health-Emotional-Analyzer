# AI-Based Mental Health Emotion Analyzer

*Understand your emotions. Track your wellbeing. Get supportive insights.*

> **Disclaimer:** This application is an educational AI-based emotional support tool. It does not provide medical or psychological diagnosis. If you are concerned about your mental health, consider speaking with a qualified professional or a trusted person.

## 1. Project description
A Flask web application that analyzes a user's **text** and **speech** to estimate a *possible emotional state* (stress, anxiety, sadness/low mood, happiness, anger, fear, neutral), shows a confidence score and probabilities, gives general wellness suggestions, tracks trends on a dashboard, and shows a gentle early-support message when several recent results are strongly negative. Privacy comes first: typed text and audio are never stored.

## 2. Features
- Register / login / logout (hashed passwords, session cookies, protected pages)
- Text emotion analysis with a pretrained **DistilBERT** model (real inference, loaded once at startup)
- Speech emotion analysis: upload (WAV, MP3, M4A, FLAC, OGG) or record in the browser; **Librosa** features + pretrained **wav2vec2** model
- Dashboard: totals, latest and most frequent emotion, average score, 3 Chart.js charts, recent table
- History: search, filter by emotion/type, delete one item, clear all
- Rule-based wellness recommendations; early-support alert; crisis-language support message
- Privacy page: what is stored, delete history, delete account
- Demo sentences, `seed-demo` command, automated tests

## 3. Technology stack
Python 3.11+, Flask, Flask-CORS, Flask-SQLAlchemy / SQLAlchemy 2, SQLite, PyTorch, Hugging Face Transformers, NLTK, Librosa, SoundFile, SpeechRecognition, NumPy, HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Chart.js.

## 4. System architecture
```
Browser (HTML/CSS/JS, Chart.js)
   |  fetch() JSON / multipart
Flask routes  (auth_routes, analysis_routes, dashboard_routes)
   |
Services: text_analyzer | speech_analyzer | recommendation_engine | privacy_service
   |                          |
models/emotion_model.py   models/speech_model.py   (Hugging Face models, loaded once)
   |
SQLAlchemy ORM -> SQLite (users, emotion_analyses)
```
**How the emotions are produced.** The text model predicts 6 base emotions (sadness, joy, love, anger, fear, surprise). The app maps them to 7: happiness = joy + love; neutral = surprise (plus extra weight when the model is unsure); **stress and anxiety are derived** by moving part of the fear/sadness/anger probability when stress words (deadline, pressure...) or anxiety words (worried, nervous...) appear. This mapping is a documented heuristic on top of real model output. The default speech model knows neutral, happy, angry and sad only; stress/anxiety/fear from voice are not predicted unless you plug in a model that supports them (or use the optional transcript).

## 5. Folder structure
```
mental-health-emotion-analyzer/
├── app.py  config.py  requirements.txt  README.md  PROJECT_DOCUMENTATION.md  .env.example  .gitignore
├── models/      emotion_model.py  speech_model.py
├── services/    text_analyzer.py  speech_analyzer.py  recommendation_engine.py  privacy_service.py
├── database/    db.py  models.py
├── routes/      auth_routes.py  analysis_routes.py  dashboard_routes.py
├── utils/       preprocessing.py  errors.py
├── templates/   base, index, login, register, dashboard, text_analysis, speech_analysis,
│                history, recommendations, about, privacy, error (.html)
├── static/      css/style.css  js/main.js  js/analysis.js  js/dashboard.js
├── uploads/     (temporary audio only, deleted after analysis)
└── tests/       conftest.py  test_app.py  test_text_analyzer.py  test_routes.py
```

## 6. Installation requirements
- Windows 10/11 (also works on macOS/Linux), **Python 3.11 or newer**
- Internet on the first run (models are downloaded once: about 250 MB text + about 380 MB speech) and for the page CDN files (Bootstrap, Chart.js, fonts)
- Optional: **FFmpeg** if you want MP3/M4A decoding to be more reliable (WAV always works)

## 7. Python installation
Download Python 3.11+ from python.org and tick **"Add python.exe to PATH"** during setup. Check with `python --version`.

## 8-10. Virtual environment and requirements (exact commands)
Open **Command Prompt** or PowerShell inside the extracted `mental-health-emotion-analyzer` folder:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
(PowerShell may need `Set-ExecutionPolicy -Scope Process RemoteSigned` once before `activate`.)

## 11. Environment variables
Copy `.env.example` to `.env` and edit (the app also runs without it, but sessions then reset on every restart):
```
copy .env.example .env
```
| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Flask session secret. Use a long random value. |
| `DATABASE_URL` | Default `sqlite:///mental_health.db` (file created in `instance/`). |
| `TEXT_MODEL_ID` / `SPEECH_MODEL_ID` | Hugging Face model names. |
| `DEMO_MODE` | `true` = never load the text model; all text results are labelled demo. |
| `ALLOW_DEMO_FALLBACK` | `true` = if the text model cannot load, use labelled demo predictions. |
| `LOAD_MODELS_ON_START` | Load models at startup (recommended). |
| `CORS_ORIGINS` | Allowed origins for `/api/*`. |
Generate a key: `python -c "import secrets; print(secrets.token_hex(32))"`

## 12. Database setup
Nothing to do: tables (`users`, `emotion_analyses`) are created automatically on first start.

## 13. How to run
```
python app.py
```
Open **http://127.0.0.1:5000**. The first start downloads the models, which can take a few minutes; the console shows progress messages. Optional development data: `flask --app app seed-demo` creates `demo@example.com` / `Demo@1234` with sample results.

Run the tests: `python -m pytest tests -v`

## 14. How to use text analysis
Register, log in, open **Analyze text**, type a few sentences (or click an example sentence) and press **Analyze Emotion**. You get the possible emotion, confidence, probabilities, an AI-generated insight and wellness tips. Only the result is saved.

## 15. How to use speech analysis
Open **Analyze speech**. Upload an audio file or press **Record with microphone** (allow the browser permission; recording is converted to WAV in the browser, so it works in Chrome, Edge and Firefox). Press **Analyze Speech**. The optional transcript checkbox sends audio to Google's speech service and is off by default.

## 16. API documentation
All state-changing requests need the header `X-Requested-With: XMLHttpRequest` (the bundled JavaScript adds it). Errors look like `{"error": "message", "code": "machine_code"}`.

| Method | Endpoint | Auth | Body / notes | Success |
|---|---|---|---|---|
| POST | `/api/register` | no | `{name, email, password}` | 201 |
| POST | `/api/login` | no | `{email, password}` | 200 |
| POST | `/api/logout` | no | | 200 |
| POST | `/api/analyze/text` | yes | `{text}` (max 2000 chars) | 200 result JSON |
| POST | `/api/analyze/speech` | yes | multipart: `audio`, optional `use_transcript=true` | 200 result JSON |
| GET | `/api/dashboard?tz_offset=` | yes | stats, charts data, alert | 200 |
| GET | `/api/history?search=&emotion=&type=&page=&per_page=` | yes | | 200 |
| DELETE | `/api/history/<id>` | yes | | 200 / 404 |
| DELETE | `/api/history` | yes | clears all | 200 |
| GET | `/api/recommendations` | no | all tips (+ latest emotion if logged in) | 200 |
| DELETE | `/api/account` | yes | `{password}` | 200 |
| GET | `/api/health` | no | DB + model status | 200 |

Status codes used: 200, 201, 400 (invalid input), 401 (not logged in), 403 (wrong password / missing header), 404, 409 (e-mail exists), 413 (file too large), 415 (unsupported audio), 422 (undecodable audio), 429 (too many login attempts), 500, 503 (model unavailable).

## 17. Screenshots (placeholders)
Add your own images to `static/images/` and link them here: Home, Text analysis result, Speech analysis result, Dashboard, History, Privacy page.

## 18. Troubleshooting
| Problem | Fix |
|---|---|
| `pip install torch` is slow/fails | Use Python 3.11/3.12 (64-bit). CPU build is enough. Retry on a stable connection. |
| Console says model could not be loaded | No internet or blocked Hugging Face. Text analysis falls back to **labelled demo predictions**. Connect and restart to download the real model. Speech returns "model unavailable". |
| First start is slow | Models are downloading (cached afterwards in your user `.cache\huggingface` folder). |
| MP3/M4A "could not be decoded" | Install FFmpeg and add it to PATH, or convert to WAV. |
| Microphone not working | Use `http://127.0.0.1:5000` (not a LAN IP), allow the permission, or upload a file. |
| Page has no styling/charts | The CDN files need internet. |
| `Activate.ps1 cannot be loaded` | Run PowerShell: `Set-ExecutionPolicy -Scope Process RemoteSigned`. |
| Logged out after each restart | Set `SECRET_KEY` in `.env`. |
| Port 5000 in use | Change the port in the last line of `app.py`. |
| Transformers error about `torch.load` | Keep the pinned `transformers<4.46` or upgrade `torch` to 2.6+. |

## 19. Privacy information
Stored: name, e-mail, password hash, and per-analysis result (emotion, confidence, probabilities, tips, time, input type). **Not stored:** typed text, audio, transcripts. Audio is deleted from `uploads/` right after analysis. No analysis content is logged. You can delete history or the whole account.

## 20. Disclaimer
This application is an educational AI-based emotional support tool. It does not provide medical or psychological diagnosis. If you are concerned about your mental health, consider speaking with a qualified professional or a trusted person. In an emergency contact your local emergency number (India: Tele-MANAS 14416).

## 21. Future scope
Train/fine-tune a model on stress and anxiety data; add a speech model with more classes (`SPEECH_MODEL_ID=ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` works with the same code); plug in your own scikit-learn speech classifier (`SPEECH_BACKEND=sklearn`, joblib bundle `{"model", "labels"}` using the 181-value Librosa vector); multilingual models (Hindi); mood journaling reminders; export reports; optional counsellor contact; mobile app.
