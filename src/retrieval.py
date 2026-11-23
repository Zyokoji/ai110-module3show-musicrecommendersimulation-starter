"""
Retrieval step for VibeMatch: a small TF-IDF search engine written in plain Python.

It searches three sources:
1. activity contexts  (data/activity_contexts.json): "study", "workout", ...
2. genre notes        (data/genre_notes.json): aliases, related genres, descriptions
3. song documents     built from data/songs.csv, enriched with the genre notes

What is retrieved changes the recommendations: the best activity context fills
in missing preferences, genre notes supply related genres, and the song-text
match becomes a "matches your words" score inside score_song().

This is classic information retrieval (TF-IDF + cosine similarity), not a
trained or generative model.
"""

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("vibematch")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "im",
    "in", "is", "it", "me", "my", "of", "on", "or", "please", "some", "something",
    "song", "songs", "music", "track", "tracks", "that", "the", "to", "want", "with",
    "need", "give", "play", "find", "like", "really", "very", "while", "when", "get",
    "can", "you", "your", "this", "playlist", "list", "good", "best", "kind", "of",
}


def stem(word: str) -> str:
    """Very small suffix stripper so 'studying' matches 'study' and 'songs' matches 'song'."""
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1] == word[-2]:  # running -> runn -> run
            word = word[:-1]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    """Lowercase, split into words, drop stopwords and stem."""
    text = text.lower().replace("lo-fi", "lofi").replace("hip-hop", "hiphop").replace("hip hop", "hiphop")
    words = re.findall(r"[a-z0-9&]+", text)
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


@dataclass
class Document:
    """One searchable item: an activity, a genre note or a song."""
    doc_id: str
    source: str
    text: str
    payload: Dict = field(default_factory=dict)


class TfidfIndex:
    """TF-IDF vectors + cosine similarity over a list of documents."""

    def __init__(self, documents: List[Document]):
        """Build the index (document frequencies, idf weights and normalized vectors)."""
        self.documents = documents
        tokenized = [tokenize(d.text) for d in documents]
        doc_freq = Counter(term for tokens in tokenized for term in set(tokens))
        n_docs = len(documents)
        self.idf = {term: math.log((n_docs + 1) / (df + 1)) + 1.0 for term, df in doc_freq.items()}
        self.vectors = [self._vector(tokens) for tokens in tokenized]

    def _vector(self, tokens: List[str]) -> Dict[str, float]:
        """Turn tokens into a unit-length TF-IDF vector (unknown words are ignored)."""
        counts = Counter(t for t in tokens if t in self.idf)
        vector = {term: count * self.idf[term] for term, count in counts.items()}
        norm = math.sqrt(sum(v * v for v in vector.values()))
        return {term: v / norm for term, v in vector.items()} if norm else {}

    def search(self, query: str, top_n: int = 5, min_score: float = 0.0) -> List[Tuple[Document, float, List[str]]]:
        """Return (document, cosine similarity, shared terms) for the best matches."""
        query_vec = self._vector(tokenize(query))
        if not query_vec:
            return []
        results = []
        for doc, vec in zip(self.documents, self.vectors):
            shared = [t for t in query_vec if t in vec]
            score = sum(query_vec[t] * vec[t] for t in shared)
            if score > min_score:
                results.append((doc, round(score, 4), sorted(shared)))
        results.sort(key=lambda r: (-r[1], r[0].doc_id))
        return results[:top_n]


def _load_json(path: str, key: str) -> List[Dict]:
    """Load a list from a knowledge-base JSON file; return [] (with a warning) if it is missing or broken."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        items = data.get(key, [])
        if not isinstance(items, list):
            raise ValueError(f"'{key}' must be a list")
        return items
    except FileNotFoundError:
        logger.warning("knowledge file %s not found; continuing without it", path)
    except (json.JSONDecodeError, ValueError, AttributeError) as error:
        logger.warning("knowledge file %s is invalid (%s); continuing without it", path, error)
    return []


class KnowledgeBase:
    """Activity contexts + genre notes + song documents, each with its own TF-IDF index."""

    def __init__(self, songs: List[Dict], genres: List[Dict], activities: List[Dict]):
        """Build the three indexes from already-loaded data."""
        self.genres = {g["name"]: g for g in genres if g.get("name")}
        self.activities = [a for a in activities if a.get("name") and a.get("keywords")]
        self.catalog_genres = {s["genre"].lower() for s in songs if s.get("genre")}

        self.activity_index = TfidfIndex([
            Document(f"activity:{a['name']}", "activity", " ".join([a["name"]] + a["keywords"]), a)
            for a in self.activities
        ])
        self.song_index = TfidfIndex([
            Document(f"song:{s['id']}", "song", self._song_text(s), s) for s in songs
        ])

    @classmethod
    def from_files(cls, songs: List[Dict], genre_path: str = "data/genre_notes.json",
                   activity_path: str = "data/activity_contexts.json") -> "KnowledgeBase":
        """Load the JSON knowledge files (missing files degrade gracefully to empty sources)."""
        return cls(songs, _load_json(genre_path, "genres"), _load_json(activity_path, "contexts"))

    def _song_text(self, song: Dict) -> str:
        """Searchable text for a song: its labels, tags, energy words and its genre's description."""
        energy = song.get("energy") or 0.5
        energy_words = ("high energy intense loud fast" if energy >= 0.75
                        else "low energy calm quiet soft slow" if energy <= 0.4 else "medium energy")
        note = self.genres.get(song.get("genre", ""), {}).get("description", "")
        parts = [song.get("title", ""), song.get("genre", ""), song.get("mood", ""),
                 " ".join(song.get("mood_tags") or []), energy_words, note]
        return " ".join(p for p in parts if p)

    # --- lookups used by the workflow -----------------------------------------

    def find_genre(self, name: str) -> Optional[Dict]:
        """Return the genre note for a genre name, or None."""
        return self.genres.get(name)

    def related_in_catalog(self, genre: str) -> List[str]:
        """Related genres from the notes that actually exist in the song catalog."""
        note = self.genres.get(genre, {})
        return [g for g in note.get("related", []) if g in self.catalog_genres and g != genre]

    def alias_table(self) -> List[Tuple[str, str]]:
        """(alias, genre name) pairs, longest alias first so 'indie pop' wins over 'pop'."""
        pairs = [(alias.lower(), g["name"]) for g in self.genres.values() for alias in g.get("aliases", [])]
        pairs += [(name, name) for name in self.catalog_genres]  # catalog genres always recognised
        return sorted(set(pairs), key=lambda p: (-len(p[0]), p[0]))

    def retrieve_context(self, query: str, min_score: float = 0.2) -> List[Tuple[Dict, float, List[str]]]:
        """Best-matching activity contexts for the query (payload, score, matched terms)."""
        return [(doc.payload, score, terms)
                for doc, score, terms in self.activity_index.search(query, top_n=3, min_score=min_score)]

    def song_relevance(self, query: str, top_n: int = 10) -> Dict[int, Dict]:
        """Song id -> {"score": 0..1 (best match = 1), "terms": shared words} for the query."""
        hits = self.song_index.search(query, top_n=top_n)
        if not hits:
            return {}
        best = hits[0][1]
        return {doc.payload["id"]: {"score": round(score / best, 2), "terms": terms}
                for doc, score, terms in hits}
