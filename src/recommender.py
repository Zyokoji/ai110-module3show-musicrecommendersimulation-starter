"""
Core logic for the Music Recommender Simulation.

The recommender is *content-based*: it compares the attributes of each song
(genre, mood, energy, ...) with a user's taste profile and gives every song
a score. The highest-scoring songs become the recommendations.

Main pieces:
- load_songs()        read data/songs.csv into a list of dictionaries
- score_song()        score ONE song for ONE user and explain the points
- rank_songs()        score EVERY song, then pick the top k (with optional
                      diversity penalty)
- recommend_songs()   simple wrapper that returns (song, score, explanation)
- SCORING_MODES       interchangeable weight "strategies" (balanced,
                      genre-first, mood-first, energy-focused)
- Song / UserProfile / Recommender   object-oriented version used by tests
"""

import csv
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Data classes (object-oriented representation)
# ---------------------------------------------------------------------------

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    # Challenge 1: advanced (simulated) features. Defaults keep old code working.
    popularity: Optional[int] = None          # 0-100, simulated
    release_decade: Optional[int] = None      # e.g. 1990, 2010
    instrumentalness: Optional[float] = None  # 0.0 (vocals) - 1.0 (no vocals)
    liveness: Optional[float] = None          # 0.0 (studio) - 1.0 (live crowd)
    mood_tags: List[str] = field(default_factory=list)  # e.g. ["calm", "study"]


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    # Optional extra preferences (None / empty = "no preference")
    target_valence: Optional[float] = None
    target_danceability: Optional[float] = None
    target_tempo_bpm: Optional[float] = None
    target_instrumentalness: Optional[float] = None
    target_liveness: Optional[float] = None
    target_popularity: Optional[int] = None
    preferred_decade: Optional[int] = None
    preferred_mood_tags: List[str] = field(default_factory=list)

    def to_prefs(self) -> Dict:
        """Convert this profile into the dictionary format used by score_song."""
        prefs = {
            "genre": self.favorite_genre,
            "mood": self.favorite_mood,
            "energy": self.target_energy,
            "likes_acoustic": self.likes_acoustic,
            "valence": self.target_valence,
            "danceability": self.target_danceability,
            "tempo_bpm": self.target_tempo_bpm,
            "instrumentalness": self.target_instrumentalness,
            "liveness": self.target_liveness,
            "popularity": self.target_popularity,
            "release_decade": self.preferred_decade,
            "mood_tags": list(self.preferred_mood_tags),
        }
        # Drop preferences the user did not set.
        return {key: value for key, value in prefs.items() if value not in (None, [])}


# ---------------------------------------------------------------------------
# Scoring modes (Challenge 2) - a simple Strategy pattern
# ---------------------------------------------------------------------------

@dataclass
class ScoringMode:
    """A named set of feature weights; swapping modes swaps the scoring strategy."""
    name: str
    description: str
    weights: Dict[str, float]


# Numeric features compared by closeness: feature -> size of its value range.
# similarity = 1 - |song value - target| / range   (never below 0)
NUMERIC_FEATURE_RANGES: Dict[str, float] = {
    "energy": 1.0,
    "valence": 1.0,
    "danceability": 1.0,
    "acousticness": 1.0,
    "instrumentalness": 1.0,
    "liveness": 1.0,
    "tempo_bpm": 120.0,   # a 120 BPM gap counts as "completely different"
    "popularity": 100.0,  # popularity is on a 0-100 scale
}

SCORING_MODES: Dict[str, ScoringMode] = {
    "balanced": ScoringMode(
        name="balanced",
        description="Starter recipe: genre +2.0, mood +1.0, energy closeness up to +1.5, "
                    "small bonuses for the other features.",
        weights={
            "genre": 2.0, "mood": 1.0, "mood_tags": 1.0,
            "energy": 1.5, "valence": 0.5, "danceability": 0.5, "acousticness": 0.5,
            "instrumentalness": 0.5, "liveness": 0.25, "tempo_bpm": 0.5,
            "popularity": 0.25, "release_decade": 0.5,
        },
    ),
    "genre-first": ScoringMode(
        name="genre-first",
        description="Genre dominates (+4.0); every other feature counts about half as much.",
        weights={
            "genre": 4.0, "mood": 0.5, "mood_tags": 0.5,
            "energy": 0.75, "valence": 0.25, "danceability": 0.25, "acousticness": 0.25,
            "instrumentalness": 0.25, "liveness": 0.1, "tempo_bpm": 0.25,
            "popularity": 0.1, "release_decade": 0.25,
        },
    ),
    "mood-first": ScoringMode(
        name="mood-first",
        description="Mood (+3.0), mood tags (up to +2.0) and valence lead; genre only +0.5.",
        weights={
            "genre": 0.5, "mood": 3.0, "mood_tags": 2.0,
            "energy": 0.75, "valence": 1.0, "danceability": 0.25, "acousticness": 0.25,
            "instrumentalness": 0.25, "liveness": 0.1, "tempo_bpm": 0.25,
            "popularity": 0.1, "release_decade": 0.25,
        },
    ),
    "energy-focused": ScoringMode(
        name="energy-focused",
        description="Energy closeness up to +4.0, tempo and danceability up to +1.0 each; "
                    "genre and mood only +0.5.",
        weights={
            "genre": 0.5, "mood": 0.5, "mood_tags": 0.25,
            "energy": 4.0, "valence": 0.25, "danceability": 1.0, "acousticness": 0.5,
            "instrumentalness": 0.25, "liveness": 0.25, "tempo_bpm": 1.0,
            "popularity": 0.1, "release_decade": 0.1,
        },
    ),
}

DEFAULT_MODE = "balanced"

# Diversity penalty defaults (Challenge 3)
DEFAULT_ARTIST_PENALTY = 1.0  # subtracted per already-selected song by the same artist
DEFAULT_GENRE_PENALTY = 0.5   # subtracted per already-selected song in the same genre


def get_mode(mode: Union[str, ScoringMode, None]) -> ScoringMode:
    """Return a ScoringMode from a mode name (or pass a ScoringMode through)."""
    if mode is None:
        return SCORING_MODES[DEFAULT_MODE]
    if isinstance(mode, ScoringMode):
        return mode
    key = str(mode).strip().lower()
    if key not in SCORING_MODES:
        valid = ", ".join(SCORING_MODES)
        raise ValueError(f"Unknown scoring mode '{mode}'. Choose one of: {valid}")
    return SCORING_MODES[key]


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["id", "title", "genre", "mood", "energy"]
INT_FIELDS = ["id", "popularity", "release_decade"]
FLOAT_FIELDS = ["energy", "tempo_bpm", "valence", "danceability", "acousticness",
                "instrumentalness", "liveness"]
UNIT_RANGE_FIELDS = ["energy", "valence", "danceability", "acousticness",
                     "instrumentalness", "liveness"]


def _parse_int(text: str) -> int:
    """Convert text like '2010' or '2010.0' to an int (raises ValueError otherwise)."""
    number = float(text)
    if not number.is_integer():
        raise ValueError(f"'{text}' is not a whole number")
    return int(number)


def _check_range(name: str, value: float) -> None:
    """Raise ValueError if a numeric value is outside the range allowed for its column."""
    if name in UNIT_RANGE_FIELDS and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name}={value} must be between 0 and 1")
    if name == "popularity" and not 0 <= value <= 100:
        raise ValueError(f"popularity={value} must be between 0 and 100")
    if name == "tempo_bpm" and value <= 0:
        raise ValueError(f"tempo_bpm={value} must be positive")


def _parse_row(row: Dict[str, str]) -> Tuple[Dict, List[str]]:
    """Turn one raw CSV row into a typed song dict; returns (song, warnings)."""
    warnings: List[str] = []
    song: Dict = {}
    for key, raw in row.items():
        if key is None:  # extra unnamed columns in a malformed row
            raise ValueError("row has more values than the header")
        text = (raw or "").strip()
        if key in INT_FIELDS or key in FLOAT_FIELDS:
            if text == "":
                if key in REQUIRED_FIELDS:
                    raise ValueError(f"missing required value '{key}'")
                song[key] = None
                warnings.append(f"'{key}' is blank (treated as unknown)")
                continue
            try:
                value = _parse_int(text) if key in INT_FIELDS else float(text)
                _check_range(key, value)
            except ValueError as error:
                if key in REQUIRED_FIELDS:
                    raise ValueError(f"invalid '{key}': {error}")
                song[key] = None
                warnings.append(f"invalid '{key}' ({error}); treated as unknown")
                continue
            song[key] = value
        elif key == "mood_tags":
            song[key] = [tag.strip().lower() for tag in text.split(";") if tag.strip()]
        else:
            if key in REQUIRED_FIELDS and text == "":
                raise ValueError(f"missing required value '{key}'")
            song[key] = text
    for key in REQUIRED_FIELDS:
        if key not in song:
            raise ValueError(f"missing required column '{key}'")
    song.setdefault("artist", "")
    song.setdefault("mood_tags", [])
    return song, warnings


def load_songs(csv_path: str) -> List[Dict]:
    """Read songs from a CSV file into a list of dicts with numbers converted to int/float."""
    songs: List[Dict] = []
    seen_ids = set()
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        # line 1 is the header, so data rows start at line 2
        for line_number, row in enumerate(reader, start=2):
            try:
                song, warnings = _parse_row(row)
            except ValueError as error:
                print(f"Warning: skipped line {line_number} of {csv_path}: {error}")
                continue
            if song["id"] in seen_ids:
                print(f"Warning: skipped line {line_number}: duplicate song id {song['id']}")
                continue
            for warning in warnings:
                print(f"Warning: line {line_number} ({song['title']}): {warning}")
            seen_ids.add(song["id"])
            songs.append(song)
    return songs


# ---------------------------------------------------------------------------
# Scoring one song
# ---------------------------------------------------------------------------

def _same_text(a, b) -> bool:
    """Case-insensitive, whitespace-insensitive comparison of two labels."""
    return str(a).strip().lower() == str(b).strip().lower()


def _numeric_targets(user_prefs: Dict) -> Dict[str, float]:
    """Collect the numeric targets the user set (likes_acoustic becomes an acousticness target)."""
    targets = {key: user_prefs[key] for key in NUMERIC_FEATURE_RANGES
               if user_prefs.get(key) is not None}
    if "acousticness" not in targets and user_prefs.get("likes_acoustic") is not None:
        targets["acousticness"] = 0.8 if user_prefs["likes_acoustic"] else 0.2
    return targets


def score_song(user_prefs: Dict, song: Dict,
               mode: Union[str, ScoringMode, None] = DEFAULT_MODE) -> Tuple[float, List[str]]:
    """Score one song against user preferences and return (score, list of reasons)."""
    weights = get_mode(mode).weights
    score = 0.0
    reasons: List[str] = []

    def add(points: float, reason: str) -> None:
        # Round each part so the reasons always add up to the displayed total.
        nonlocal score
        points = round(points, 2)
        if points > 0:
            score += points
            reasons.append(f"{reason} (+{points:.2f})")

    # 1) Categorical matches: all-or-nothing points.
    if user_prefs.get("genre") and song.get("genre") and _same_text(user_prefs["genre"], song["genre"]):
        add(weights.get("genre", 0), f"genre match: {song['genre']}")
    if user_prefs.get("mood") and song.get("mood") and _same_text(user_prefs["mood"], song["mood"]):
        add(weights.get("mood", 0), f"mood match: {song['mood']}")

    # 2) Detailed mood tags: share of the user's tags that the song also has.
    raw_tags = user_prefs.get("mood_tags") or []
    if isinstance(raw_tags, str):  # allow "calm;study" as well as ["calm", "study"]
        raw_tags = raw_tags.replace(",", ";").split(";")
    wanted_tags = [t.strip().lower() for t in raw_tags if t.strip()]
    if wanted_tags:
        matched = [t for t in wanted_tags if t in song.get("mood_tags", [])]
        if matched:
            fraction = len(matched) / len(wanted_tags)
            add(weights.get("mood_tags", 0) * fraction,
                f"mood tags {', '.join(matched)} ({len(matched)}/{len(wanted_tags)})")

    # 3) Numeric features: reward CLOSENESS to the target, not bigger/smaller values.
    for feature, target in _numeric_targets(user_prefs).items():
        value = song.get(feature)
        if value is None:
            continue  # unknown value -> no points, no penalty
        similarity = max(0.0, 1.0 - abs(value - target) / NUMERIC_FEATURE_RANGES[feature])
        add(weights.get(feature, 0) * similarity,
            f"{feature} {value:g} vs target {target:g} ({similarity:.0%} similar)")

    # 4) Release decade: full points for the same decade, half for a neighbouring one.
    wanted_decade = user_prefs.get("release_decade")
    song_decade = song.get("release_decade")
    if wanted_decade is not None and song_decade is not None:
        gap = abs(song_decade - wanted_decade)
        if gap == 0:
            add(weights.get("release_decade", 0), f"from the {song_decade}s")
        elif gap == 10:
            add(weights.get("release_decade", 0) * 0.5, f"from the {song_decade}s (next to {wanted_decade}s)")

    return round(score, 2), reasons


# ---------------------------------------------------------------------------
# Ranking many songs
# ---------------------------------------------------------------------------

def _diversity_penalty(song: Dict, selected: List[Dict],
                       artist_penalty: float, genre_penalty: float) -> Tuple[float, List[str]]:
    """Penalty for repeating an artist/genre that is ALREADY in the selected list."""
    penalty = 0.0
    notes: List[str] = []
    artist = (song.get("artist") or "").strip()
    if artist:  # songs with no artist are never penalised for "repeating" an artist
        repeats = sum(1 for s in selected if _same_text(s.get("artist") or "", artist))
        if repeats:
            amount = artist_penalty * repeats
            penalty += amount
            notes.append(f"diversity penalty: artist {artist} already listed {repeats}x (-{amount:.2f})")
    genre = (song.get("genre") or "").strip()
    if genre:
        repeats = sum(1 for s in selected if _same_text(s.get("genre") or "", genre))
        if repeats:
            amount = genre_penalty * repeats
            penalty += amount
            notes.append(f"diversity penalty: genre {genre} already listed {repeats}x (-{amount:.2f})")
    return round(penalty, 2), notes


def rank_songs(user_prefs: Dict, songs: List[Dict], k: int = 5,
               mode: Union[str, ScoringMode, None] = DEFAULT_MODE,
               diversity: bool = False,
               artist_penalty: float = DEFAULT_ARTIST_PENALTY,
               genre_penalty: float = DEFAULT_GENRE_PENALTY) -> List[Dict]:
    """Score every song and return the top k as dicts with base score, penalty, final score and reasons."""
    if k <= 0:
        return []

    # Step 1: score every song once (skipping duplicate ids so nothing appears twice).
    candidates: List[Dict] = []
    seen_ids = set()
    for song in songs:
        song_id = song.get("id", id(song))
        if song_id in seen_ids:
            continue
        seen_ids.add(song_id)
        base_score, reasons = score_song(user_prefs, song, mode)
        candidates.append({"song": song, "base_score": base_score, "reasons": reasons})

    # Step 2a: no diversity -> plain sort, highest score first.
    # sorted() returns a NEW list and leaves `candidates` untouched;
    # list.sort() would reorder the original list in place.
    if not diversity:
        ranked = sorted(candidates, key=lambda c: (-c["base_score"], c["song"].get("title", "")))
        return [{**c, "penalty": 0.0, "final_score": c["base_score"]} for c in ranked[:k]]

    # Step 2b: diversity -> greedy re-ranking. Each round, every remaining song's
    # score is reduced based on the songs ALREADY selected, and the best one is picked.
    selected: List[Dict] = []
    # Keep the pool in title order so ties are broken alphabetically (max() keeps the first).
    remaining = sorted(candidates, key=lambda c: c["song"].get("title", ""))
    while remaining and len(selected) < k:
        already_picked = [s["song"] for s in selected]
        options = []
        for cand in remaining:
            penalty, notes = _diversity_penalty(cand["song"], already_picked,
                                                artist_penalty, genre_penalty)
            final = round(cand["base_score"] - penalty, 2)
            options.append((final, cand, penalty, notes))
        # Highest final score wins; if tied, the higher base score wins.
        final, cand, penalty, notes = max(options, key=lambda o: (o[0], o[1]["base_score"]))
        remaining.remove(cand)
        selected.append({**cand, "penalty": penalty, "final_score": final,
                         "reasons": cand["reasons"] + notes})
    return selected


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5,
                    mode: Union[str, ScoringMode, None] = DEFAULT_MODE,
                    diversity: bool = False) -> List[Tuple[Dict, float, str]]:
    """Return the top k songs as (song, final score, explanation) tuples, best first."""
    results = rank_songs(user_prefs, songs, k=k, mode=mode, diversity=diversity)
    return [(r["song"], r["final_score"], "; ".join(r["reasons"]) or "no matching features")
            for r in results]


# ---------------------------------------------------------------------------
# Object-oriented wrapper (used by tests/test_recommender.py)
# ---------------------------------------------------------------------------

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song], mode: Union[str, ScoringMode] = DEFAULT_MODE):
        """Store the catalog of Song objects and the scoring mode to use."""
        self.songs = songs
        self.mode = mode

    def recommend(self, user: UserProfile, k: int = 5, diversity: bool = False) -> List[Song]:
        """Return the top k Song objects for this user, best first."""
        by_id = {song.id: song for song in self.songs}
        results = rank_songs(user.to_prefs(), [asdict(s) for s in self.songs],
                             k=k, mode=self.mode, diversity=diversity)
        return [by_id[r["song"]["id"]] for r in results]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a readable sentence explaining why this song got its score."""
        score, reasons = score_song(user.to_prefs(), asdict(song), self.mode)
        detail = "; ".join(reasons) if reasons else "no matching features"
        return f"Score {score:.2f}: {detail}"
