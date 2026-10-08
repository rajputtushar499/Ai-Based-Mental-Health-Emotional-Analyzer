"""Speech emotion models behind one small interface.

To use your own model, create a class with the same two members
(`load()` and `predict_proba(y, sr, features)`) and select it in `build_speech_model`.

Backends:
  * HuggingFaceSpeechModel (default) - wav2vec2 audio-classification model from the Hub.
  * SklearnSpeechModel - optional: a scikit-learn classifier you trained yourself on
    Librosa feature vectors (e.g. from RAVDESS). See README "Future scope / own model".
"""
import os
import threading

import numpy as np

TARGET_SR = 16000


class HuggingFaceSpeechModel:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.extractor = None
        self.model = None
        self.labels = []
        self.load_error = None
        self._torch = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        with self._lock:
            if self.is_loaded:
                return True
            try:
                import torch
                from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

                self._torch = torch
                self.extractor = AutoFeatureExtractor.from_pretrained(self.model_id)
                self.model = AutoModelForAudioClassification.from_pretrained(self.model_id)
                self.model.eval()
                id2label = self.model.config.id2label
                self.labels = [str(id2label[i]).lower() for i in range(len(id2label))]
                self.load_error = None
                return True
            except Exception as exc:
                self.model = None
                self.load_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                return False

    def predict_proba(self, y: np.ndarray, sr: int, features=None) -> dict:
        if not self.is_loaded:
            raise RuntimeError("Speech emotion model is not loaded.")
        torch = self._torch
        inputs = self.extractor(y, sampling_rate=sr, return_tensors="pt", padding=True)
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1).tolist()
        return {label: float(p) for label, p in zip(self.labels, probs)}


class SklearnSpeechModel:
    """Loads a joblib file saved as {"model": fitted_classifier, "labels": [...]}.

    The classifier must accept the 181-value feature vector produced by
    `services.speech_analyzer.extract_features` (40 MFCC + 12 chroma + 128 mel + 1 ZCR).
    """

    def __init__(self, path: str):
        self.path = path
        self.model = None
        self.labels = []
        self.load_error = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        try:
            if not os.path.exists(self.path):
                raise FileNotFoundError(f"No model file at {self.path}")
            import joblib

            bundle = joblib.load(self.path)
            self.model, self.labels = bundle["model"], [str(x).lower() for x in bundle["labels"]]
            self.load_error = None
            return True
        except Exception as exc:
            self.model = None
            self.load_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            return False

    def predict_proba(self, y, sr, features=None) -> dict:
        if not self.is_loaded or features is None:
            raise RuntimeError("Speech emotion model is not loaded.")
        probs = self.model.predict_proba(features.reshape(1, -1))[0]
        return {label: float(p) for label, p in zip(self.labels, probs)}


def build_speech_model(config):
    if config.get("SPEECH_BACKEND", "huggingface") == "sklearn":
        return SklearnSpeechModel(config["SPEECH_SKLEARN_MODEL_PATH"])
    return HuggingFaceSpeechModel(config["SPEECH_MODEL_ID"])
