"""Unit tests for preprocessing, the emotion mapping layer and the recommendation engine."""
import pytest

from config import TestConfig
from services.recommendation_engine import EMOTIONS, get_recommendation, recommendation_text
from services.text_analyzer import TextAnalyzer, map_to_app_emotions
from utils.errors import AnalysisError
from utils.preprocessing import clean_text, stemmed_tokens


@pytest.fixture()
def analyzer():
    return TextAnalyzer({k: getattr(TestConfig, k) for k in dir(TestConfig) if k.isupper()})


def test_clean_text_removes_urls_and_emails():
    out = clean_text("Mail me a@b.com see https://x.com   soooooo   bad!!!!!!")
    assert "@" not in out and "http" not in out and "  " not in out


def test_demo_analysis_is_labelled(analyzer):
    result = analyzer.analyze("I feel happy today because I completed my project.")
    assert result["demo"] is True
    assert result["emotion"] == "happiness"
    assert abs(sum(result["scores"].values()) - 1) < 1e-6


def test_stress_and_anxiety_cues(analyzer):
    assert analyzer.analyze("I have been feeling stressed because of too much work.")["emotion"] == "stress"
    assert analyzer.analyze("I am worried about my upcoming examination.")["emotion"] == "anxiety"


def test_validation(analyzer):
    with pytest.raises(AnalysisError):
        analyzer.analyze("   ")
    with pytest.raises(AnalysisError):
        analyzer.analyze("a" * 5000)
    with pytest.raises(AnalysisError):
        analyzer.analyze(123)


def test_mapping_uses_model_probabilities_and_sums_to_one():
    raw = {"sadness": 0.1, "joy": 0.05, "love": 0.0, "anger": 0.05, "fear": 0.78, "surprise": 0.02}
    scores = map_to_app_emotions(raw, stemmed_tokens("I am so worried"))
    assert scores["anxiety"] > scores["fear"]
    assert abs(sum(scores.values()) - 1) < 1e-6


def test_low_confidence_moves_towards_neutral():
    raw = {"sadness": 0.2, "joy": 0.2, "love": 0.1, "anger": 0.2, "fear": 0.2, "surprise": 0.1}
    scores = map_to_app_emotions(raw, [])
    assert max(scores, key=scores.get) in ("neutral", "happiness")


def test_every_emotion_has_recommendation():
    for emo in EMOTIONS:
        assert get_recommendation(emo)["tips"]
        assert recommendation_text(emo)
