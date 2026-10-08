"""Speech emotion analysis.

Pipeline: audio file -> decode/resample (Librosa) -> trim/validate -> Librosa features
(MFCC, mel spectrogram, zero-crossing rate, chroma) -> speech emotion model ->
map labels to the app's emotions -> (optional) transcript + text model fusion.

Honest note: the default pretrained model (wav2vec2, "superb-er") knows 4 emotions:
neutral, happy, angry, sad. It cannot detect stress/anxiety/fear from the voice alone.
When the optional transcript is enabled, the text model adds those signals.
"""
import os

import numpy as np

from models.speech_model import TARGET_SR, build_speech_model
from utils.errors import AnalysisError, InvalidAudioError, ModelUnavailableError

EMOTIONS = ["stress", "anxiety", "sadness", "happiness", "anger", "fear", "neutral"]

# Label names used by common speech-emotion models -> app emotions
LABEL_MAP = {
    "neu": "neutral", "neutral": "neutral", "calm": "neutral", "surprised": "neutral", "surprise": "neutral",
    "hap": "happiness", "happy": "happiness", "happiness": "happiness", "joy": "happiness",
    "ang": "anger", "angry": "anger", "anger": "anger", "disgust": "anger",
    "sad": "sadness", "sadness": "sadness",
    "fea": "fear", "fear": "fear", "fearful": "fear",
}

_SIGNATURES = {
    "wav": lambda h: h[:4] == b"RIFF",
    "mp3": lambda h: h[:3] == b"ID3" or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0),
    "m4a": lambda h: h[4:8] == b"ftyp",
    "flac": lambda h: h[:4] == b"fLaC",
    "ogg": lambda h: h[:4] == b"OggS",
}


def has_valid_signature(path: str, extension: str) -> bool:
    """Check the first bytes of the file really look like the claimed audio format."""
    check = _SIGNATURES.get(extension)
    try:
        with open(path, "rb") as fh:
            header = fh.read(12)
    except OSError:
        return False
    return bool(check and len(header) >= 4 and check(header))


def extract_features(y: np.ndarray, sr: int):
    """Return (feature_vector[181], summary_dict) using Librosa."""
    import librosa

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    stft = np.abs(librosa.stft(y))
    chroma = librosa.feature.chroma_stft(S=stft, sr=sr)
    mel = librosa.feature.melspectrogram(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)
    rms = librosa.feature.rms(y=y)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)

    vector = np.hstack([mfcc.mean(axis=1), chroma.mean(axis=1), mel.mean(axis=1), zcr.mean(axis=1)]).astype(np.float32)
    summary = {
        "mfcc_coefficients": int(mfcc.shape[0]),
        "mel_bands": int(mel.shape[0]),
        "chroma_bins": int(chroma.shape[0]),
        "zero_crossing_rate": round(float(zcr.mean()), 4),
        "energy_rms": round(float(rms.mean()), 4),
        "spectral_centroid_hz": round(float(centroid.mean()), 1),
    }
    return vector, summary


def _map_labels(raw: dict) -> dict:
    scores = {e: 0.0 for e in EMOTIONS}
    for label, prob in raw.items():
        scores[LABEL_MAP.get(label.lower(), "neutral")] += prob
    total = sum(scores.values()) or 1.0
    return {e: v / total for e, v in scores.items()}


class SpeechAnalyzer:
    def __init__(self, config, text_analyzer=None):
        self.config = config
        self.model = build_speech_model(config)
        self.text_analyzer = text_analyzer

    def load(self) -> None:
        print("[speech] Loading speech emotion model (first run downloads it)...")
        if self.model.load():
            print("[speech] Model ready.")
        else:
            print(f"[speech] Model could not be loaded: {self.model.load_error}")
            print("[speech] Speech analysis will answer with a clear 'model unavailable' message.")

    def status(self) -> dict:
        return {"model_id": self.config["SPEECH_MODEL_ID"], "backend": self.config["SPEECH_BACKEND"],
                "loaded": self.model.is_loaded, "error": None if self.model.is_loaded else self.model.load_error}

    # ------------------------------------------------------------------
    def _load_audio(self, path: str):
        try:
            import librosa

            y, sr = librosa.load(path, sr=TARGET_SR, mono=True, duration=self.config["MAX_AUDIO_SECONDS"])
        except Exception:
            raise InvalidAudioError("This audio file could not be decoded. Try a WAV file "
                                    "(MP3/M4A decoding may need FFmpeg installed).")
        if y.size == 0:
            raise InvalidAudioError("The audio file is empty.")
        duration = float(len(y) / sr)
        if duration < self.config["MIN_AUDIO_SECONDS"]:
            raise InvalidAudioError("The recording is too short. Please record at least 1 second of speech.")
        if float(np.sqrt(np.mean(y ** 2))) < 1e-4:
            raise InvalidAudioError("The recording seems to be silent. Please check your microphone.")
        return y, sr, duration

    def _transcribe(self, y: np.ndarray, sr: int):
        """Optional: speech-to-text with the SpeechRecognition package (needs internet)."""
        import tempfile

        import soundfile as sf
        import speech_recognition as sr_lib

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=self.config["UPLOAD_FOLDER"])
        tmp.close()
        try:
            sf.write(tmp.name, y, sr)
            recognizer = sr_lib.Recognizer()
            with sr_lib.AudioFile(tmp.name) as source:
                audio = recognizer.record(source)
            return recognizer.recognize_google(audio)
        except Exception:
            return None
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    def analyze(self, path: str, use_transcript: bool = False) -> dict:
        if not self.model.is_loaded:
            raise ModelUnavailableError(
                "The speech emotion model is not available (it must be downloaded once - see README > Troubleshooting).")
        y, sr, duration = self._load_audio(path)
        try:
            features, summary = extract_features(y, sr)
        except Exception:
            raise InvalidAudioError("Audio features could not be extracted from this file.")
        try:
            raw = self.model.predict_proba(y, sr, features)
        except Exception:
            raise AnalysisError("The speech emotion model failed to process this audio.", 500, "model_error")

        scores = _map_labels(raw)
        transcript_used = False
        if use_transcript and self.text_analyzer is not None:
            transcript = self._transcribe(y, sr)
            if transcript:
                try:
                    text_result = self.text_analyzer.analyze(transcript)
                    if not text_result["demo"]:  # only fuse real model output
                        scores = {e: 0.65 * scores[e] + 0.35 * text_result["scores"][e] for e in EMOTIONS}
                        transcript_used = True
                except AnalysisError:
                    pass
            del transcript  # never stored or returned

        emotion = max(scores, key=scores.get)
        return {"emotion": emotion, "confidence": scores[emotion], "scores": scores, "demo": False,
                "model": self.config["SPEECH_MODEL_ID"], "duration": round(duration, 2),
                "features": summary, "transcript_used": transcript_used, "raw_labels": raw}
