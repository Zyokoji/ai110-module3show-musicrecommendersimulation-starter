"""
Rule-based parser that turns a plain-English request into explicit preferences.

Example: "upbeat 90s jazz but no lofi" ->
    genre=jazz, mood=happy, release_decade=1990, exclude_genres=["lofi"]

It uses keyword lists (no machine learning). Anything it does not recognise is
left for the retrieval step, which searches the knowledge base with the full text.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# word -> catalog mood
MOOD_WORDS = {
    "happy": "happy", "upbeat": "happy", "cheerful": "happy", "joyful": "happy", "feel good": "happy",
    "feel-good": "happy", "sunny": "happy",
    "sad": "sad", "depressing": "sad", "heartbroken": "sad",
    "chill": "chill", "chilled": "chill", "laid back": "chill", "laid-back": "chill",
    "relaxed": "relaxed", "relaxing": "relaxed",
    "intense": "intense", "hard": "intense", "heavy": "intense",
    "angry": "angry", "furious": "angry", "rage": "angry",
    "romantic": "romantic",
    "nostalgic": "nostalgic", "throwback": "nostalgic",
    "euphoric": "euphoric",
    "confident": "confident", "swagger": "confident",
    "focused": "focused",
    "moody": "moody", "brooding": "moody",
    "melancholic": "melancholic", "melancholy": "melancholic",
}

# phrase -> energy target (checked longest phrase first)
ENERGY_WORDS = {
    "high energy": 0.9, "high-energy": 0.9, "energetic": 0.88, "pumped": 0.92, "hype": 0.9,
    "low energy": 0.25, "low-energy": 0.25, "calm": 0.3, "quiet": 0.25, "soft": 0.3,
    "gentle": 0.3, "mellow": 0.35, "medium energy": 0.55, "moderate": 0.55,
}

NEGATIONS = r"(?:no|not|without|except|avoid|skip|minus|but not|nothing)"

DECADE_PATTERN = re.compile(r"\b(19[5-9]0|20[0-2]0|[5-9]0|00|10|20)'?s\b")
ENERGY_NUMBER = re.compile(r"\benergy\s*(?:of|=|:)?\s*(0?\.\d+|1(?:\.0+)?|0)\b")


@dataclass
class ParsedQuery:
    """What the parser understood, plus a log of how it decided."""
    text: str
    genre: Optional[str] = None
    genre_in_catalog: bool = True
    mood: Optional[str] = None
    energy: Optional[float] = None
    release_decade: Optional[int] = None
    exclude_genres: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def explicit_prefs(self) -> Dict:
        """Preferences the user stated directly (these override retrieved context)."""
        prefs: Dict = {}
        if self.genre:
            prefs["genre"] = self.genre
        if self.mood:
            prefs["mood"] = self.mood
        if self.energy is not None:
            prefs["energy"] = self.energy
        if self.release_decade is not None:
            prefs["release_decade"] = self.release_decade
        return prefs


def _decade_from(token: str) -> int:
    """'90' -> 1990, '00' -> 2000, '2010' -> 2010."""
    if len(token) == 4:
        return int(token)
    value = int(token)
    return 2000 + value if value <= 20 else 1900 + value


def _find_phrase(text: str, phrase: str) -> Optional[re.Match]:
    """Find a whole-word phrase in text."""
    return re.search(r"(?<![a-z0-9&])" + re.escape(phrase) + r"(?![a-z0-9&])", text)


def _is_negated(text: str, start: int) -> bool:
    """True if a negation word is one of the 2 words right before position `start`.

    A short window keeps "no lofi, just jazz" from also excluding jazz.
    """
    window = " ".join(text[:start].split()[-2:])
    return re.search(r"\b" + NEGATIONS + r"\b", window) is not None


def parse_query(text: str, alias_table: List[Tuple[str, str]], catalog_genres: set) -> ParsedQuery:
    """Extract genre, mood, energy, decade and excluded genres from a request."""
    lowered = text.lower()
    parsed = ParsedQuery(text=text)

    # Genres: longest alias first; a negated alias becomes an exclusion.
    taken = []  # character spans already used by a longer alias
    for alias, genre in alias_table:
        for match in re.finditer(r"(?<![a-z0-9&])" + re.escape(alias) + r"(?![a-z0-9&])", lowered):
            if any(s <= match.start() < e for s, e in taken):
                continue
            taken.append((match.start(), match.end()))
            if _is_negated(lowered, match.start()):
                if genre not in parsed.exclude_genres:
                    parsed.exclude_genres.append(genre)
                    parsed.notes.append(f"'{alias}' is negated -> exclude genre {genre}")
            elif parsed.genre is None:
                parsed.genre = genre
                parsed.genre_in_catalog = genre in catalog_genres
                parsed.notes.append(f"'{alias}' -> genre {genre}"
                                    + ("" if parsed.genre_in_catalog else " (not in catalog)"))

    # Mood: first non-negated mood word.
    for word in sorted(MOOD_WORDS, key=len, reverse=True):
        match = _find_phrase(lowered, word)
        if match and parsed.mood is None:
            if _is_negated(lowered, match.start()):
                parsed.notes.append(f"'{word}' is negated -> mood not set")
                continue
            parsed.mood = MOOD_WORDS[word]
            parsed.notes.append(f"'{word}' -> mood {parsed.mood}")

    # Energy: an explicit number wins over words.
    number = ENERGY_NUMBER.search(lowered)
    if number:
        parsed.energy = float(number.group(1))
        parsed.notes.append(f"explicit energy {parsed.energy:g}")
    else:
        for phrase in sorted(ENERGY_WORDS, key=len, reverse=True):
            match = _find_phrase(lowered, phrase)
            if match and not _is_negated(lowered, match.start()):
                parsed.energy = ENERGY_WORDS[phrase]
                parsed.notes.append(f"'{phrase}' -> energy {parsed.energy:g}")
                break

    decade = DECADE_PATTERN.search(lowered)
    if decade:
        parsed.release_decade = _decade_from(decade.group(1))
        parsed.notes.append(f"'{decade.group(0)}' -> decade {parsed.release_decade}s")

    return parsed
