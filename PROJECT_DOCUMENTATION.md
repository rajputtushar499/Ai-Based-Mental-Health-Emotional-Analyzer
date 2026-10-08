# AI-Based Mental Health Emotion Analyzer - Project Documentation

> Educational project. It does not provide medical or psychological diagnosis.

## 1. Abstract
This project is a web application that estimates the possible emotional state of a user from written text and recorded speech. A pretrained DistilBERT model classifies text, a pretrained wav2vec2 model classifies speech, and Librosa extracts acoustic features. Results are turned into wellness insights, trend charts and a gentle early-support message. Only results are stored; text and audio are discarded after analysis.

## 2. Introduction
Stress, anxiety and low mood are common among students. Many people do not notice patterns in their own emotions. Natural Language Processing (NLP) and speech processing can give a simple, private, self-awareness tool.

## 3. Problem statement
Students lack an easy, private way to reflect on and track their emotional state, and existing tools often store sensitive text or claim medical accuracy.

## 4. Objectives
- Analyze emotions from text and speech using real AI models.
- Show confidence and probabilities clearly.
- Give general wellness suggestions and trends over time.
- Protect privacy (no raw text/audio storage).
- Never present results as a diagnosis.

## 5. Existing system
Mood journals and surveys (manual, no AI), general chatbots (no tracking, privacy unclear), clinical screening tools (need professionals).

## 6. Proposed system
A Flask web app with login, text and speech analyzers, a rule-based recommendation engine, a dashboard with charts, history management and privacy controls.

## 7. System architecture
Browser -> Flask routes (REST JSON) -> services (text, speech, recommendations, privacy) -> AI models (loaded once) and SQLAlchemy/SQLite. See README section 4.

## 8. Modules
1. **Authentication** - register, login, logout, sessions, password hashing.
2. **Text analyzer** - cleaning, DistilBERT inference, emotion mapping.
3. **Speech analyzer** - audio decoding, Librosa features, wav2vec2 inference.
4. **Recommendation engine** - rules per emotion, insight text, early-support alert.
5. **Dashboard and history** - statistics, charts, search/filter/delete.
6. **Privacy module** - temp file deletion, data deletion, crisis-language message.

## 9. Technologies used
Python, Flask, Flask-CORS, SQLAlchemy, SQLite, PyTorch, Transformers, NLTK, Librosa, SoundFile, SpeechRecognition, HTML, CSS, JavaScript, Bootstrap, Chart.js.

## 10. AI / NLP methodology
1. **Preprocessing:** Unicode normalisation, remove URLs/e-mails, shorten repeated characters, trim spaces.
2. **Tokenisation:** the model's WordPiece tokenizer converts text to token IDs.
3. **Inference:** DistilBERT outputs one score per base emotion; softmax turns scores into probabilities that sum to 1.
4. **Mapping:** 6 base emotions -> 7 app emotions (see below).
5. **Decision:** the highest probability is the possible emotion; that probability is the confidence.

Mapping: happiness = joy + love; neutral = surprise (+ extra weight if the model is unsure); stress and anxiety are *derived* using NLTK-stemmed cue words that move part of the fear/sadness/anger probability. This is a transparent heuristic, listed as a limitation.

## 11. BERT explanation (simple)
BERT is a Transformer language model trained on huge amounts of text to understand context: the word "bank" is read differently in "river bank" and "bank loan". Self-attention lets each word look at all other words. DistilBERT is a smaller, faster version (about 40% smaller) that keeps most of the accuracy. We use a DistilBERT already fine-tuned on an emotion dataset, so we only run inference (no training needed).

## 12. Speech Emotion Recognition explanation
Voice carries emotion in pitch, energy, speed and tone. Steps: load audio at 16 kHz -> check length and silence -> extract **MFCC** (shape of the vocal spectrum), **mel spectrogram** (energy per frequency band), **zero-crossing rate** (noisiness) and **chroma** (pitch classes) with Librosa -> a pretrained wav2vec2 model (self-supervised on raw audio, fine-tuned for emotion) outputs probabilities for neutral, happy, angry, sad. The Librosa features are shown to the user and also feed the optional scikit-learn backend. An optional transcript (SpeechRecognition) lets the text model add stress/anxiety signals.

## 13. Database design
**users**(id PK, name, e-mail unique, password_hash, created_at)
**emotion_analyses**(id PK, user_id FK -> users.id, input_type, emotion, confidence, emotion_scores JSON text, recommendation, is_demo, audio_duration, created_at)
Relationship: one user has many analyses; deleting a user cascades. No raw text/audio columns exist.

## 14. API design
REST + JSON, session cookie auth, consistent error body `{error, code}`, proper status codes. Full list in README section 16.

## 15. Security
Werkzeug password hashing; secret key in environment; input validation; upload extension + magic-byte check, random file names, 16 MB limit; SQLAlchemy parameterised queries; CORS limited to configured origins; HttpOnly + SameSite cookies; required `X-Requested-With` header on state-changing API calls (CSRF defence); login rate limiting; no stack traces to users; no sensitive logging.

## 16. Privacy
Data minimisation (results only), temporary audio deleted in a `finally` block, user-controlled deletion of history and account, transcript option off by default and clearly explained.

## 17. Advantages
Real model inference; privacy-friendly; simple UI; modular code; works offline after the first model download (except CDN assets); honest labelling of demo mode.

## 18. Limitations
Models are trained on specific datasets (mostly English, acted speech) and can be wrong; stress/anxiety are heuristic; speech model has 4 classes; short texts are ambiguous; not clinically validated; the early-support rule is simple; wellbeing score is a simple formula.

## 19. Future scope
Fine-tune on stress/anxiety data, multilingual (Hindi) models, more speech classes, personalised trends, journaling reminders, export, deployment with HTTPS and a production server.

## 20. Conclusion
The project shows how NLP and speech processing can support emotional self-awareness while respecting privacy and being clear that it is not a diagnostic tool.

## 21. Viva questions and answers
1. **What does your project do?** It estimates the possible emotion from text or speech, shows confidence, gives wellness tips and tracks trends.
2. **Is it a diagnosis tool?** No. It gives screening-style wellness insight only, and the UI says so.
3. **Which AI model analyzes text?** A DistilBERT model fine-tuned for emotion classification from Hugging Face.
4. **What is BERT?** A Transformer language model that understands word context using self-attention.
5. **Why DistilBERT?** Smaller and faster than BERT with similar accuracy, good for a laptop.
6. **Did you train the model?** No, we use a pretrained model for inference; training needs large labelled data and GPU time.
7. **How do you get stress and anxiety if the model has no such labels?** We map the base emotions and use cue words to re-assign part of fear/sadness/anger probability. It is a documented heuristic.
8. **What is a confidence score?** The model's probability for the top emotion.
9. **What is softmax?** A function turning raw scores into probabilities that add to 1.
10. **What are MFCCs?** Numbers describing the shape of the sound spectrum, widely used for speech.
11. **What is a mel spectrogram?** Energy of the sound over time on a scale that matches human hearing.
12. **Which speech model do you use?** wav2vec2 fine-tuned for emotion (neutral, happy, angry, sad).
13. **Why are Librosa features extracted if wav2vec2 uses raw audio?** They are validated, shown to the user and used by the optional scikit-learn backend; the interface lets any model be plugged in.
14. **How is privacy protected?** Text and audio are not stored, temporary audio is deleted, users can delete history/account, passwords are hashed.
15. **How are passwords stored?** As salted hashes with Werkzeug, never plain text.
16. **Why SQLite and SQLAlchemy?** SQLite needs no server; SQLAlchemy ORM gives safe queries and clean models.
17. **How is SQL injection prevented?** ORM parameterised queries.
18. **What happens if the model cannot download?** Text analysis uses clearly labelled demo predictions; speech shows a friendly "model unavailable" message.
19. **How does the early-support alert work?** If at least 80% of the latest 5 results (within 14 days, minimum 3) have 60%+ negative emotion probability, a supportive message appears.
20. **What are the limitations?** Model errors, heuristic stress/anxiety, limited speech classes, not clinically validated.
21. **How could you improve accuracy?** Fine-tune on stress/anxiety data, add more speech classes, use multilingual models, collect consented feedback.
22. **Why is the model loaded at startup?** Loading takes seconds; doing it once keeps requests fast.
