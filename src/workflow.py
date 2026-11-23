"""
VibeMatch recommendation workflow: a fixed sequence of steps that turns a
plain-English request into explained recommendations, recording every
decision in a trace.

    1. validate     guardrails on the raw input
    2. parse        rule-based keyword parser (genre, mood, energy, decade, exclusions)
    3. retrieve     TF-IDF search of the knowledge base (activity context + song text)
    4. build_prefs  merge retrieved context with explicit words; add related genres
    5. constrain    remove excluded genres from the candidate songs
    6. rank         Module 3 scoring + ranking (score_song / rank_songs)
    7. self_check   output guardrails + confidence score + warnings about likely causes
    8. explain      short summary of the top reasons for each song

The steps and their order are fixed in code (no language model decides them).
Running with use_retrieval=False skips step 3 and the related-genre lookup,
which gives the keyword-only BASELINE used in the evaluation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.guardrails import (GuardrailError, check_results, clean_preferences, query_flags,
                            validate_k, validate_query)
from src.query_parser import parse_query
from src.recommender import DEFAULT_MODE, get_mode, max_possible_score, rank_songs
from src.retrieval import KnowledgeBase

logger = logging.getLogger("vibematch")

HIGH_CONFIDENCE = 0.7
MEDIUM_CONFIDENCE = 0.45


@dataclass
class TraceStep:
    """One recorded step: what it was, what it decided, and supporting details."""
    step: str
    decision: str
    details: Dict = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Everything the workflow produced for one request."""
    query: str
    prefs: Dict
    recommendations: List[Dict]
    confidence: float
    confidence_label: str
    warnings: List[str]
    trace: List[TraceStep]
    context: Optional[str] = None
    use_retrieval: bool = True


def summarize_reasons(reasons: List[str], limit: int = 3) -> str:
    """Pick the highest-scoring reasons and join them into one short sentence."""
    scored = []
    for reason in reasons:
        match = re.search(r"\(\+(\d+\.\d+)\)$", reason)
        if match:
            scored.append((float(match.group(1)), reason[:match.start()].strip()))
    scored.sort(key=lambda item: -item[0])
    if not scored:
        return "No strong match; included as a closest available option."
    return "Top reasons: " + "; ".join(text for _, text in scored[:limit]) + "."


def _mood_energy_conflict(prefs: Dict) -> bool:
    """True when the requested mood and energy point in opposite directions."""
    mood, energy = prefs.get("mood"), prefs.get("energy")
    if mood is None or energy is None:
        return False
    return ((mood in {"sad", "melancholic", "chill", "relaxed"} and energy >= 0.75)
            or (mood in {"intense", "angry", "euphoric"} and energy <= 0.3))


class RecommendationWorkflow:
    """Runs the 8 steps for a request against one song catalog and knowledge base."""

    def __init__(self, songs: List[Dict], knowledge: KnowledgeBase):
        """Keep the catalog and knowledge base for repeated runs."""
        self.songs = songs
        self.knowledge = knowledge
        self.catalog_moods = {s["mood"].lower() for s in songs if s.get("mood")}

    def run(self, query: str, k: int = 5, mode: str = DEFAULT_MODE,
            diversity: bool = True, use_retrieval: bool = True) -> WorkflowResult:
        """Run the workflow; raises GuardrailError if the request is rejected."""
        trace: List[TraceStep] = []
        warnings: List[str] = []
        label = "workflow" if use_retrieval else "baseline"

        # 1. validate --------------------------------------------------------
        try:
            query = validate_query(query)
            k = validate_k(k)
            mode_obj = get_mode(mode)
        except GuardrailError as error:
            logger.warning("[%s] request rejected (%s): %s", label, error.code, error.message)
            raise
        except ValueError as error:  # unknown scoring mode
            logger.warning("[%s] request rejected (bad_mode): %s", label, error)
            raise GuardrailError("bad_mode", str(error)) from error
        warnings.extend(query_flags(query))
        trace.append(TraceStep("validate", "request accepted",
                               {"query": query, "k": k, "mode": mode_obj.name, "diversity": diversity}))
        logger.info("[%s] query=%r k=%d mode=%s", label, query, k, mode_obj.name)

        # 2. parse -----------------------------------------------------------
        parsed = parse_query(query, self.knowledge.alias_table(), self.knowledge.catalog_genres)
        trace.append(TraceStep("parse", f"found {len(parsed.explicit_prefs())} explicit preference(s)",
                               {"explicit": parsed.explicit_prefs(), "exclude_genres": parsed.exclude_genres,
                                "notes": parsed.notes}))

        # 3. retrieve --------------------------------------------------------
        context, relevance = None, {}
        if use_retrieval:
            contexts = self.knowledge.retrieve_context(query)
            relevance = self.knowledge.song_relevance(query)
            if contexts:
                context = contexts[0][0]
            trace.append(TraceStep(
                "retrieve",
                f"best context: {context['name']}" if context else "no activity context matched",
                {"contexts": [{"name": c["name"], "score": s, "matched": t} for c, s, t in contexts],
                 "top_song_matches": {sid: r for sid, r in list(relevance.items())[:5]}}))
        else:
            trace.append(TraceStep("retrieve", "skipped (baseline: keywords only)"))

        # 4. build preferences ------------------------------------------------
        prefs: Dict = {}
        sources: Dict[str, str] = {}
        if context:
            for key, value in context["prefs"].items():
                prefs[key] = value
                sources[key] = f"context '{context['name']}'"
        for key, value in parsed.explicit_prefs().items():
            prefs[key] = value  # the user's own words beat retrieved defaults
            sources[key] = "your words"
        if use_retrieval and parsed.genre:
            related = [g for g in self.knowledge.related_in_catalog(parsed.genre)
                       if g not in parsed.exclude_genres]  # never suggest a genre the user ruled out
            if related:
                prefs["related_genres"] = related
                sources["related_genres"] = f"genre notes for {parsed.genre}"
            if not parsed.genre_in_catalog:
                prefs.pop("genre", None)
                sources.pop("genre", None)
                warnings.append(f"'{parsed.genre}' is not in the catalog; using related genres "
                                f"{', '.join(related) or '(none)'} instead.")
        if relevance:
            prefs["retrieval_scores"] = relevance
            sources["retrieval_scores"] = "song text search"
        prefs, pref_warnings = clean_preferences(prefs)
        warnings.extend(pref_warnings)
        if not any(key != "retrieval_scores" for key in prefs) and not relevance:
            error = GuardrailError("no_preferences",
                                   "I couldn't find a genre, mood, energy level or activity in that request. "
                                   "Try something like 'calm music for studying' or 'upbeat pop'.")
            logger.warning("[%s] request rejected (no_preferences): %r", label, query)
            raise error
        shown = {key: value for key, value in prefs.items() if key != "retrieval_scores"}
        trace.append(TraceStep("build_prefs", f"{len(shown)} preference(s) set",
                               {"prefs": shown, "sources": sources}))

        # 5. constrain -------------------------------------------------------
        excluded = {g.lower() for g in parsed.exclude_genres}
        candidates = [s for s in self.songs if s["genre"].lower() not in excluded]
        trace.append(TraceStep("constrain",
                               f"removed {len(self.songs) - len(candidates)} song(s) from excluded genres"
                               if excluded else "no exclusions",
                               {"exclude_genres": sorted(excluded), "candidates": len(candidates)}))

        # 6. rank -------------------------------------------------------------
        ranked = rank_songs(prefs, candidates, k=k, mode=mode_obj, diversity=diversity)
        results = [r for r in ranked if r["base_score"] > 0]  # never recommend a song with no match
        trace.append(TraceStep("rank", f"ranked {len(candidates)} songs, kept top {len(results)}",
                               {"top": [(r["song"]["title"], r["final_score"]) for r in results]}))

        # 7. self-check ----------------------------------------------------------
        problems = check_results(results, k, parsed.exclude_genres)
        max_score = max_possible_score(prefs, mode_obj)
        top_score = results[0]["base_score"] if results else 0.0
        confidence = round(min(1.0, top_score / max_score), 2) if max_score else 0.0
        conf_label = ("high" if confidence >= HIGH_CONFIDENCE
                      else "medium" if confidence >= MEDIUM_CONFIDENCE else "low")
        if parsed.genre and not parsed.genre_in_catalog and conf_label == "high":
            conf_label = "medium"  # never claim high confidence for a genre we do not have
        if parsed.mood and parsed.mood not in self.catalog_moods:
            warnings.append(f"No song in the catalog has the mood '{parsed.mood}'.")
        if _mood_energy_conflict(prefs):
            warnings.append(f"Your mood ({prefs['mood']}) and energy ({prefs['energy']:g}) point in "
                            "different directions, so results are a compromise.")
        if conf_label == "low":
            warnings.append("Low confidence: no song in this small catalog matches the request well.")
        warnings.extend(p for p in problems if p.startswith("only "))
        hard_problems = [p for p in problems if not p.startswith("only ")]
        if hard_problems:  # should never happen; logged loudly if it does
            logger.error("[%s] output guardrail failed: %s", label, hard_problems)
            warnings.extend(f"Output check failed: {p}" for p in hard_problems)
        trace.append(TraceStep("self_check", f"confidence {confidence:.2f} ({conf_label})",
                               {"top_score": top_score, "max_possible": max_score,
                                "problems": problems}))
        logger.info("[%s] confidence=%.2f (%s) warnings=%d", label, confidence, conf_label, len(warnings))

        # 8. explain --------------------------------------------------------------
        for result in results:
            result["summary"] = summarize_reasons(result["reasons"])
        trace.append(TraceStep("explain", "added a one-line summary to each recommendation"))

        return WorkflowResult(query=query, prefs=shown, recommendations=results,
                              confidence=confidence, confidence_label=conf_label,
                              warnings=warnings, trace=trace,
                              context=context["name"] if context else None,
                              use_retrieval=use_retrieval)


def build_workflow(songs_path: str = "data/songs.csv", genre_path: str = "data/genre_notes.json",
                   activity_path: str = "data/activity_contexts.json") -> RecommendationWorkflow:
    """Load the catalog and knowledge base from disk and return a ready workflow."""
    from src.recommender import load_songs
    songs = load_songs(songs_path)
    if not songs:
        raise FileNotFoundError(f"No valid songs could be loaded from {songs_path}")
    knowledge = KnowledgeBase.from_files(songs, genre_path, activity_path)
    return RecommendationWorkflow(songs, knowledge)
