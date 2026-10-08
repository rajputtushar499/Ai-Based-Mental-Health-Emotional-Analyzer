"""Rule-based wellness recommendations, insight text and the early-support alert.

IMPORTANT: this is general wellness guidance for an educational project. It is not
medical advice and it does not diagnose any condition.
"""
from datetime import timedelta

EMOTIONS = ["stress", "anxiety", "sadness", "happiness", "anger", "fear", "neutral"]
NEGATIVE_EMOTIONS = {"stress", "anxiety", "sadness", "anger", "fear"}

DISPLAY_NAMES = {
    "stress": "Stress", "anxiety": "Anxiety", "sadness": "Sadness / low mood",
    "happiness": "Happiness", "anger": "Anger", "fear": "Fear", "neutral": "Neutral",
}

RECOMMENDATIONS = {
    "stress": {
        "title": "Ease the pressure",
        "tips": ["Take short breaks during work or study",
                 "Practice slow breathing (inhale 4s, exhale 6s)",
                 "Maintain a regular sleep schedule",
                 "Talk to someone you trust"],
    },
    "anxiety": {
        "title": "Settle your mind",
        "tips": ["Try a grounding exercise (name 5 things you can see, 4 you can touch, 3 you can hear)",
                 "Take a short break away from screens",
                 "Reduce overwhelming tasks by splitting them into small steps",
                 "Consider talking with a trusted person"],
    },
    "sadness": {
        "title": "Be gentle with yourself",
        "tips": ["Stay connected with supportive people",
                 "Maintain regular daily activities",
                 "Take care of sleep, food and hydration",
                 "Consider seeking support if these feelings persist"],
    },
    "happiness": {
        "title": "Keep the good momentum",
        "tips": ["Continue the healthy activities that help you",
                 "Maintain your social connections",
                 "Record positive moments in a journal"],
    },
    "anger": {
        "title": "Cool down before reacting",
        "tips": ["Pause before reacting",
                 "Take some quiet time",
                 "Practice slow breathing",
                 "Talk about the situation calmly when you are ready"],
    },
    "fear": {
        "title": "Feel safer and steadier",
        "tips": ["Name what you are afraid of - writing it down can make it smaller",
                 "Use slow breathing or a grounding exercise",
                 "Share your worry with someone you trust",
                 "Focus on the next small step you can control"],
    },
    "neutral": {
        "title": "Keep your routine steady",
        "tips": ["Continue regular healthy routines",
                 "Track your emotions over time to notice patterns"],
    },
}

GENERAL_NOTE = ("These are general wellness suggestions, not medical treatment. "
                "If you are concerned about your mental health, consider speaking with "
                "a qualified professional or a trusted person.")

ALERT_MESSAGE = ("Your recent emotional results suggest you may be going through a difficult period. "
                 "Consider talking with a trusted person or qualified mental-health professional.")


def get_recommendation(emotion: str) -> dict:
    rec = RECOMMENDATIONS.get(emotion, RECOMMENDATIONS["neutral"])
    return {"title": rec["title"], "tips": list(rec["tips"]), "note": GENERAL_NOTE}


def recommendation_text(emotion: str) -> str:
    """Compact text version stored in the database / shown in the history table."""
    rec = get_recommendation(emotion)
    return f"{rec['title']}: " + " • ".join(rec["tips"])


def all_recommendations() -> list:
    return [{"emotion": e, "name": DISPLAY_NAMES[e], **get_recommendation(e)} for e in EMOTIONS]


def wellbeing_score(scores: dict) -> float:
    """0-100 'emotional score': happiness counts fully, neutral partly, the rest as 0."""
    return round(100 * (scores.get("happiness", 0.0) + 0.6 * scores.get("neutral", 0.0)), 1)


def negative_load(scores: dict) -> float:
    return sum(scores.get(e, 0.0) for e in NEGATIVE_EMOTIONS)


def generate_insight(emotion, confidence, scores, input_type, demo=False) -> str:
    """Human-readable, carefully worded insight (screening style, never a diagnosis)."""
    source = "text you shared" if input_type == "text" else "voice recording"
    name = DISPLAY_NAMES.get(emotion, emotion).lower()
    parts = [f"The {source} shows signals of a possible {name} emotional state "
             f"(confidence {round(confidence * 100)}%)."]
    if confidence < 0.5:
        parts.append("Confidence is fairly low, so please treat this result with extra caution.")
    others = sorted(((k, v) for k, v in scores.items() if k != emotion and v >= 0.10),
                    key=lambda kv: kv[1], reverse=True)[:2]
    if others:
        parts.append("Other signals: " + ", ".join(f"{k} ({round(v * 100)}%)" for k, v in others) + ".")
    parts.append("This is a wellness insight from an educational AI tool, not a diagnosis.")
    if demo:
        parts.append("(Demo prediction - the AI model was not used.)")
    return " ".join(parts)


def early_support_alert(analyses, now=None):
    """Return an alert dict if recent results are consistently strongly negative.

    Rule: look at the latest 5 analyses from the last 14 days. If there are at least 3 and
    at least 80% of them have a negative-emotion load >= 60%, show a supportive message.
    `analyses` must be ordered newest first and expose .scores and .created_at.
    """
    from database.models import utcnow

    now = now or utcnow()
    recent = [a for a in analyses if a.created_at >= now - timedelta(days=14)][:5]
    if len(recent) < 3:
        return None
    high = sum(1 for a in recent if negative_load(a.scores) >= 0.6)
    if high / len(recent) >= 0.8:
        return {"level": "support", "message": ALERT_MESSAGE, "based_on": len(recent)}
    return None
