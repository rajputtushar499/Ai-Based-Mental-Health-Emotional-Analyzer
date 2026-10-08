"""Text emotion model: a DistilBERT classifier from the Hugging Face Hub.

The model is downloaded automatically the first time (about 250 MB) and cached by
Hugging Face. It is loaded ONCE when the server starts and reused for every request.
Base labels of the default model: sadness, joy, love, anger, fear, surprise.
"""
import threading

# Order used by the original "emotion" dataset, used only if the model config has generic names.
_DEFAULT_LABELS = ["sadness", "joy", "love", "anger", "fear", "surprise"]


class EmotionModel:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.tokenizer = None
        self.model = None
        self.labels = []
        self.load_error = None
        self._lock = threading.Lock()
        self._torch = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self) -> bool:
        """Load tokenizer + model. Returns True on success; stores the error otherwise."""
        with self._lock:
            if self.is_loaded:
                return True
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                self._torch = torch
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                self.model = AutoModelForSequenceClassification.from_pretrained(self.model_id)
                self.model.eval()
                id2label = self.model.config.id2label
                labels = [str(id2label[i]).lower() for i in range(len(id2label))]
                if all(label.startswith("label_") for label in labels) and len(labels) == len(_DEFAULT_LABELS):
                    labels = list(_DEFAULT_LABELS)
                self.labels = labels
                self.load_error = None
                return True
            except Exception as exc:  # no internet, missing package, corrupt cache, ...
                self.model = None
                self.tokenizer = None
                self.load_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                return False

    def predict_proba(self, text: str) -> dict:
        """Return {base_label: probability} for the given (already cleaned) text."""
        if not self.is_loaded:
            raise RuntimeError("Text emotion model is not loaded.")
        torch = self._torch
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            logits = self.model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1).tolist()
        return {label: float(p) for label, p in zip(self.labels, probs)}
