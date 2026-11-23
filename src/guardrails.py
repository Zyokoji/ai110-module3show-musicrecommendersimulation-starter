"""
Guardrails for VibeMatch: check inputs before the workflow runs and check
outputs before they are shown.

Input guardrails reject bad requests with a clear GuardrailError.
Preference guardrails drop or flag impossible values instead of crashing.
Output guardrails verify that the final list obeys the user's constraints.
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger("vibematch")

MAX_QUERY_LENGTH = 300
MIN_K, MAX_K = 1, 20

# value ranges allowed for numeric preferences
PREF_RANGES = {
    "energy": (0.0, 1.0), "valence": (0.0, 1.0), "danceability": (0.0, 1.0),
    "acousticness": (0.0, 1.0), "instrumentalness": (0.0, 1.0), "liveness": (0.0, 1.0),
    "tempo_bpm": (40.0, 220.0), "popularity": (0.0, 100.0),
}
VALID_DECADES = {1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020}
KNOWN_KEYS = set(PREF_RANGES) | {"genre", "mood", "mood_tags", "release_decade", "likes_acoustic",
                                 "related_genres", "retrieval_scores", "exclude_genres"}

# Phrases that suggest the user may be in crisis. The system still recommends
# music, but it also shows a short supportive note (it never tries to diagnose).
CRISIS_PATTERNS = [r"\bkill myself\b", r"\bsuicid", r"\bwant to die\b", r"\bend my life\b",
                   r"\bself[- ]?harm\b", r"\bhurt myself\b"]
WELLBEING_NOTE = ("It sounds like things might be really hard right now. Music can help, but you "
                  "don't have to go through it alone. In the US you can call or text 988 (Suicide & "
                  "Crisis Lifeline); elsewhere, please contact local emergency services or someone you trust.")

# Phrases that look like instructions to a chatbot. There is no language model
# here, so they cannot change behaviour; we just say they were treated as words.
INSTRUCTION_PATTERNS = [r"\bignore (all |the )?(previous|above|prior)\b", r"\bsystem prompt\b",
                        r"\byou are now\b", r"\bdisregard\b"]


class GuardrailError(ValueError):
    """Raised when a request is rejected; `code` is a short machine-readable reason."""

    def __init__(self, code: str, message: str):
        """Store the reason code and a user-friendly message."""
        super().__init__(message)
        self.code = code
        self.message = message


def validate_query(query) -> str:
    """Return a cleaned query string or raise GuardrailError."""
    if not isinstance(query, str):
        raise GuardrailError("not_text", "The request must be text.")
    cleaned = " ".join(query.split())
    if not cleaned:
        raise GuardrailError("empty_query", "Please describe what you want to listen to.")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise GuardrailError("query_too_long",
                             f"Please keep the request under {MAX_QUERY_LENGTH} characters "
                             f"(got {len(cleaned)}).")
    if len(re.findall(r"[A-Za-z]", cleaned)) < 2:
        raise GuardrailError("no_words", "The request needs at least one real word, e.g. 'chill jazz'.")
    return cleaned


def validate_k(k) -> int:
    """Return k as an int between MIN_K and MAX_K or raise GuardrailError."""
    if isinstance(k, bool) or not isinstance(k, int):
        raise GuardrailError("bad_k", "The number of songs must be a whole number.")
    if not MIN_K <= k <= MAX_K:
        raise GuardrailError("bad_k", f"The number of songs must be between {MIN_K} and {MAX_K} (got {k}).")
    return k


def query_flags(query: str) -> List[str]:
    """Notes about the query itself (crisis language, chatbot-style instructions)."""
    lowered = query.lower()
    notes = []
    if any(re.search(p, lowered) for p in CRISIS_PATTERNS):
        notes.append(WELLBEING_NOTE)
        logger.warning("crisis-language guardrail triggered")
    if any(re.search(p, lowered) for p in INSTRUCTION_PATTERNS):
        notes.append("Your request contained instruction-like text. This system has no chatbot to "
                     "instruct; it was treated as ordinary search words.")
        logger.warning("instruction-like text guardrail triggered")
    return notes


def clean_preferences(prefs: Dict) -> Tuple[Dict, List[str]]:
    """Drop unknown keys and out-of-range values; return (clean prefs, warnings)."""
    clean: Dict = {}
    warnings: List[str] = []
    for key, value in prefs.items():
        if key not in KNOWN_KEYS:
            warnings.append(f"ignored unknown preference '{key}'")
            continue
        if key in PREF_RANGES:
            low, high = PREF_RANGES[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                warnings.append(f"ignored {key}={value!r} (not a number)")
                continue
            if not low <= value <= high:
                warnings.append(f"ignored {key}={value} (must be between {low:g} and {high:g})")
                continue
        if key == "release_decade" and value not in VALID_DECADES:
            warnings.append(f"ignored release_decade={value} (not a supported decade)")
            continue
        clean[key] = value
    for warning in warnings:
        logger.warning("preference guardrail: %s", warning)
    return clean, warnings


def check_results(results: List[Dict], k: int, exclude_genres: List[str]) -> List[str]:
    """Return a list of problems with the final recommendations (empty list = all good)."""
    problems = []
    ids = [r["song"]["id"] for r in results]
    if len(ids) != len(set(ids)):
        problems.append("duplicate songs in results")
    excluded = {g.lower() for g in exclude_genres}
    if any(r["song"]["genre"].lower() in excluded for r in results):
        problems.append("an excluded genre appeared in results")
    if any(not r.get("reasons") for r in results):
        problems.append("a recommendation has no explanation")
    scores = [r["final_score"] for r in results]
    if scores != sorted(scores, reverse=True):
        problems.append("results are not sorted by score")
    if len(results) < k:
        problems.append(f"only {len(results)} of {k} requested songs could be recommended")
    return problems
