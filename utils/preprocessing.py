"""Text preprocessing helpers (cleaning + tokenising + stemming)."""
import re
import unicodedata

try:  # NLTK's tokenizer/stemmer used here need no extra data downloads
    from nltk.stem import PorterStemmer
    from nltk.tokenize import TreebankWordTokenizer

    _stemmer = PorterStemmer()
    _tokenizer = TreebankWordTokenizer()
except Exception:  # pragma: no cover - NLTK missing: fall back to plain regex
    _stemmer = None
    _tokenizer = None

_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_REPEAT_CHAR_RE = re.compile(r"(.)\1{3,}")
_REPEAT_PUNCT_RE = re.compile(r"([!?.,])\1{2,}")
_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z']+")


def clean_text(text: str) -> str:
    """Light cleaning that keeps the sentence readable for a BERT-style model.

    - normalises unicode, removes control characters
    - removes URLs and e-mail addresses (privacy)
    - shortens exaggerated repetition ("soooooo" -> "sooo", "!!!!!" -> "!!!")
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = _CONTROL_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = _REPEAT_CHAR_RE.sub(r"\1\1\1", text)
    text = _REPEAT_PUNCT_RE.sub(r"\1\1\1", text)
    return _SPACE_RE.sub(" ", text).strip()


def stem_word(word: str) -> str:
    return _stemmer.stem(word) if _stemmer else word


def tokenize(text: str) -> list:
    """Lower-case word tokens (letters/apostrophes only)."""
    text = text.lower()
    tokens = _tokenizer.tokenize(text) if _tokenizer else text.split()
    words = []
    for token in tokens:
        words.extend(_WORD_RE.findall(token))
    return words


def stemmed_tokens(text: str) -> list:
    return [stem_word(t) for t in tokenize(text)]
