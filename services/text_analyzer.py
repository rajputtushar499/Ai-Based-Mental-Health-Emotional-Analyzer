"""Text emotion analysis.

Pipeline: validate -> clean -> DistilBERT probabilities -> map to the app's 7 emotions
-> pick top emotion + confidence.

HOW THE 7 EMOTIONS ARE PRODUCED (honest description)
The pretrained model predicts 6 base emotions: sadness, joy, love, anger, fear, surprise.
  * happiness = joy + love          * sadness / anger / fear = same labels
  * neutral   = surprise + (extra weight when the model is unsure of every emotion)
  * stress / anxiety are NOT model outputs. They are derived: when the text contains
    stress words (deadline, pressure, overwhelmed...) or anxiety words (worried, nervous...),
    part of the model's fear / sadness / anger probability is re-assigned to stress / anxiety.
This mapping layer is a documented heuristic on top of real model inference.

If the model cannot be loaded, labelled DEMO predictions from a small word list are used.
"""
from services.privacy_service import contains_crisis_language
from utils.errors import AnalysisError
from utils.preprocessing import clean_text, stem_word, stemmed_tokens

EMOTIONS = ["stress", "anxiety", "sadness", "happiness", "anger", "fear", "neutral"]

_STRESS_WORDS = ["stress", "stressed", "pressure", "overwhelmed", "deadline", "deadlines", "workload",
                 "burnout", "exhausted", "overworked", "swamped", "hectic", "strain", "frazzled",
                 "drained", "tired", "busy"]
_ANXIETY_WORDS = ["anxious", "anxiety", "worried", "worry", "worrying", "nervous", "panic", "panicking",
                  "uneasy", "restless", "dread", "apprehensive", "jittery", "overthinking", "edge"]
_DEMO_WORDS = {
    "happiness": ["happy", "glad", "joy", "great", "wonderful", "excited", "proud", "love", "good", "grateful", "completed", "smile"],
    "sadness": ["sad", "down", "lonely", "cry", "crying", "hopeless", "empty", "unhappy", "miserable", "depressed", "lost"],
    "anger": ["angry", "furious", "mad", "annoyed", "irritated", "hate", "rage", "unfair"],
    "fear": ["afraid", "scared", "terrified", "frightened", "fear", "danger"],
}

STRESS_STEMS = {stem_word(w) for w in _STRESS_WORDS}
ANXIETY_STEMS = {stem_word(w) for w in _ANXIETY_WORDS}
DEMO_STEMS = {emo: {stem_word(w) for w in words} for emo, words in _DEMO_WORDS.items()}


def map_to_app_emotions(raw: dict, tokens: list) -> dict:
    """Convert the model's base-label probabilities to the app's 7 emotion scores."""
    stress_hits = sum(1 for t in tokens if t in STRESS_STEMS)
    anxiety_hits = sum(1 for t in tokens if t in ANXIETY_STEMS)

    scores = {e: 0.0 for e in EMOTIONS}
    scores["happiness"] = raw.get("joy", 0.0) + raw.get("love", 0.0)
    scores["sadness"] = raw.get("sadness", 0.0)
    scores["anger"] = raw.get("anger", 0.0)
    scores["fear"] = raw.get("fear", 0.0)
    scores["neutral"] = raw.get("surprise", 0.0)

    if anxiety_hits:  # fear-like signal + anxiety words -> anxiety
        share = min(0.9, 0.35 + 0.25 * anxiety_hits)
        moved = scores["fear"] * share
        scores["fear"] -= moved
        scores["anxiety"] += moved
    if stress_hits:  # negative signal + stress words -> stress
        share = min(0.85, 0.4 * stress_hits)
        for emo in ("fear", "sadness", "anger", "anxiety"):
            moved = scores[emo] * share
            scores[emo] -= moved
            scores["stress"] += moved

    if raw and max(raw.values()) < 0.55:  # the model is unsure about every emotion
        shift = 0.35
        for emo in EMOTIONS:
            if emo != "neutral":
                moved = scores[emo] * shift
                scores[emo] -= moved
                scores["neutral"] += moved

    total = sum(scores.values()) or 1.0
    return {e: v / total for e, v in scores.items()}


def demo_scores(tokens: list) -> dict:
    """Very small word-list scorer used ONLY in labelled demo mode."""
    scores = {e: 0.05 for e in EMOTIONS}
    scores["neutral"] = 0.6
    for emo, stems in DEMO_STEMS.items():
        scores[emo] += 0.6 * sum(1 for t in tokens if t in stems)
    scores["stress"] += 0.7 * sum(1 for t in tokens if t in STRESS_STEMS)
    scores["anxiety"] += 0.7 * sum(1 for t in tokens if t in ANXIETY_STEMS)
    total = sum(scores.values())
    return {e: v / total for e, v in scores.items()}


class TextAnalyzer:
    def __init__(self, config):
        from models.emotion_model import EmotionModel

        self.config = config
        self.model = EmotionModel(config["TEXT_MODEL_ID"])
        self.demo_forced = bool(config.get("DEMO_MODE"))
        self.allow_fallback = bool(config.get("ALLOW_DEMO_FALLBACK", True))

    def load(self) -> None:
        if self.demo_forced:
            print("[text] DEMO_MODE is on - the AI model will not be used.")
            return
        print(f"[text] Loading model '{self.config['TEXT_MODEL_ID']}' (first run downloads it)...")
        if self.model.load():
            print("[text] Model ready.")
        else:
            print(f"[text] Model could not be loaded: {self.model.load_error}")
            if self.allow_fallback:
                print("[text] Using labelled DEMO predictions instead. See README > Troubleshooting.")

    @property
    def using_demo(self) -> bool:
        return self.demo_forced or not self.model.is_loaded

    def status(self) -> dict:
        return {"model_id": self.config["TEXT_MODEL_ID"], "loaded": self.model.is_loaded,
                "demo": self.using_demo, "error": None if self.model.is_loaded else self.model.load_error}

    def analyze(self, text) -> dict:
        if not isinstance(text, str):
            raise AnalysisError("Text must be a string.", 400, "invalid_text")
        if len(text) > self.config["MAX_TEXT_LENGTH"] * 2:  # check the raw length first (cleaning shortens text)
            raise AnalysisError(f"Text is too long. Please keep it under {self.config['MAX_TEXT_LENGTH']} characters.",
                                400, "text_too_long")
        cleaned = clean_text(text)
        if len(cleaned) < self.config["MIN_TEXT_LENGTH"]:
            raise AnalysisError("Please enter some text to analyze.", 400, "empty_text")
        if len(cleaned) > self.config["MAX_TEXT_LENGTH"]:
            raise AnalysisError(f"Text is too long. Please keep it under {self.config['MAX_TEXT_LENGTH']} characters.",
                                400, "text_too_long")
        tokens = stemmed_tokens(cleaned)

        if self.using_demo:
            if self.demo_forced is False and not self.allow_fallback:
                raise AnalysisError("The AI model is not available and demo fallback is disabled.", 503, "model_unavailable")
            scores, demo, model_name = demo_scores(tokens), True, "demo word-list scorer (no AI model)"
        else:
            try:
                scores = map_to_app_emotions(self.model.predict_proba(cleaned), tokens)
            except Exception:
                raise AnalysisError("The emotion model failed to process this text.", 500, "model_error")
            demo, model_name = False, self.config["TEXT_MODEL_ID"]

        emotion = max(scores, key=scores.get)
        return {"emotion": emotion, "confidence": scores[emotion], "scores": scores, "demo": demo,
                "model": model_name, "crisis": contains_crisis_language(cleaned)}
