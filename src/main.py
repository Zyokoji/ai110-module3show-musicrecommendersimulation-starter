"""
Command line runner for the Music Recommender Simulation (CLI-first).

Examples (run from the project root):
    python -m src.main                         # default pop/happy profile, balanced mode
    python -m src.main --mode mood-first       # switch scoring mode
    python -m src.main --profile all           # every evaluation profile, top 5 each
    python -m src.main --profile chill-lofi --no-diversity
    python -m src.main --compare-modes         # same profile, all four modes side by side
    python -m src.main --diversity-demo        # top 5 with vs without the diversity penalty
    python -m src.main --experiment            # weight-shift experiment (energy x2, genre x0.5)
    python -m src.main --list                  # list profiles and modes
"""

import argparse
import textwrap
from typing import Dict, List

try:
    from src.recommender import (SCORING_MODES, DEFAULT_MODE, ScoringMode,
                                 load_songs, rank_songs)
except ModuleNotFoundError:  # allows `python src/main.py` as well
    from recommender import (SCORING_MODES, DEFAULT_MODE, ScoringMode,
                             load_songs, rank_songs)

DATA_PATH = "data/songs.csv"

# ---------------------------------------------------------------------------
# User profiles
# Keys match the song columns: categorical keys must match exactly,
# numeric keys are TARGET values (closer = more points).
# ---------------------------------------------------------------------------

PROFILES: Dict[str, Dict] = {
    # Default profile used when no --profile is given.
    "default": {
        "label": "Default: Happy Pop",
        "prefs": {
            "genre": "pop", "mood": "happy", "energy": 0.8,
            "valence": 0.8, "danceability": 0.8, "likes_acoustic": False,
            "mood_tags": ["uplifting", "sunny", "carefree"],
            "popularity": 75, "release_decade": 2010,
        },
    },
    # --- Three distinct "normal" listeners -----------------------------------
    "high-energy-pop": {
        "label": "High-Energy Pop",
        "prefs": {
            "genre": "pop", "mood": "intense", "energy": 0.92,
            "danceability": 0.85, "tempo_bpm": 130,
            "mood_tags": ["pumped", "party"], "popularity": 80, "release_decade": 2020,
        },
    },
    "chill-lofi": {
        "label": "Chill Lofi",
        "prefs": {
            "genre": "lofi", "mood": "chill", "energy": 0.35,
            "acousticness": 0.8, "instrumentalness": 0.9, "tempo_bpm": 75,
            "mood_tags": ["calm", "study", "rainy"], "release_decade": 2020,
        },
    },
    "deep-intense-rock": {
        "label": "Deep Intense Rock",
        "prefs": {
            "genre": "rock", "mood": "intense", "energy": 0.9,
            "valence": 0.4, "tempo_bpm": 150, "liveness": 0.3,
            "mood_tags": ["aggressive", "adrenaline"], "release_decade": 2000,
        },
    },
    # --- Adversarial / edge-case profiles ------------------------------------
    "sad-but-hyper": {
        "label": "Edge: High Energy + Sad Mood (conflicting)",
        "prefs": {
            "genre": "folk", "mood": "sad", "energy": 0.95, "valence": 0.1,
            "tempo_bpm": 160,
        },
    },
    "boundary-silence": {
        "label": "Edge: Boundary Targets (all 0.0 / 1.0, no genre or mood)",
        "prefs": {
            "energy": 0.0, "valence": 0.0, "acousticness": 1.0,
            "instrumentalness": 1.0, "danceability": 0.0,
        },
    },
    "ghost-genre": {
        "label": "Edge: Unknown Genre + Messy Input ('k-pop', ' HAPPY ')",
        "prefs": {"genre": "k-pop", "mood": " HAPPY ", "energy": 0.6},
    },
}

EVALUATION_ORDER = ["default", "high-energy-pop", "chill-lofi", "deep-intense-rock",
                    "sad-but-hyper", "boundary-silence", "ghost-genre"]

# Weight-shift experiment (Phase 4, Step 3): energy doubled, genre halved.
EXPERIMENT_MODE = ScoringMode(
    name="experiment: energy x2, genre x0.5",
    description="Balanced weights, but energy 1.5 -> 3.0 and genre 2.0 -> 1.0.",
    weights={**SCORING_MODES["balanced"].weights, "energy": 3.0, "genre": 1.0},
)


# ---------------------------------------------------------------------------
# Plain-Python ASCII table (Challenge 4) - no extra libraries needed
# ---------------------------------------------------------------------------

def format_table(headers: List[str], rows: List[List], widths: List[int]) -> str:
    """Build an ASCII table; each cell may be a string or a list of lines, long text is wrapped."""
    def cell_lines(value, width):
        parts = value if isinstance(value, list) else [str(value)]
        lines: List[str] = []
        for part in parts:
            lines.extend(textwrap.wrap(str(part), width, subsequent_indent="  ") or [""])
        return lines

    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [border,
           "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |",
           border.replace("-", "=")]
    for row in rows:
        columns = [cell_lines(value, w) for value, w in zip(row, widths)]
        height = max(len(c) for c in columns)
        for i in range(height):
            out.append("| " + " | ".join((c[i] if i < len(c) else "").ljust(w)
                                         for c, w in zip(columns, widths)) + " |")
        out.append(border)
    return "\n".join(out)


def describe_prefs(prefs: Dict) -> str:
    """One-line summary of a preference dictionary."""
    return ", ".join(f"{key}={value}" for key, value in prefs.items())


def recommendation_table(results: List[Dict]) -> str:
    """Turn rank_songs() results into the summary table (title, score, reasons)."""
    rows = []
    for rank, r in enumerate(results, start=1):
        song = r["song"]
        score_cell = [f"{r['final_score']:.2f}"]
        if r["penalty"]:
            score_cell.append(f"(base {r['base_score']:.2f})")
        rows.append([
            rank,
            [song["title"], f"by {song.get('artist') or 'unknown'}"],
            [song.get("genre", ""), song.get("mood", "")],
            score_cell,
            r["reasons"] or ["no matching features"],
        ])
    return format_table(["#", "Song", "Genre / Mood", "Score", "Why (points earned)"],
                        rows, [2, 22, 12, 12, 62])


def print_profile(key: str, songs: List[Dict], mode, k: int, diversity: bool) -> List[Dict]:
    """Rank songs for one profile and print a titled table."""
    profile = PROFILES[key]
    mode_name = mode.name if isinstance(mode, ScoringMode) else mode
    results = rank_songs(profile["prefs"], songs, k=k, mode=mode, diversity=diversity)
    print(f"\n=== Profile: {profile['label']} ===")
    print(f"Preferences : {describe_prefs(profile['prefs'])}")
    print(f"Scoring mode: {mode_name} | Diversity penalty: {'ON' if diversity else 'OFF'} | Top {k}")
    print(recommendation_table(results))
    return results


def short(result: Dict) -> str:
    """'Title (score)' label for compact comparison tables."""
    return f"{result['song']['title']} ({result['final_score']:.2f})"


def compare_columns(title: str, columns: Dict[str, List[Dict]], k: int) -> None:
    """Print a compact rank-by-rank comparison of several result lists."""
    headers = ["#"] + list(columns)
    rows = []
    for i in range(k):
        rows.append([i + 1] + [short(c[i]) if i < len(c) else "-" for c in columns.values()])
    width = max(24, min(30, 100 // max(1, len(columns))))
    print(f"\n--- {title} ---")
    print(format_table(headers, rows, [2] + [width] * len(columns)))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Read command line options."""
    parser = argparse.ArgumentParser(description="CLI-first music recommender simulation")
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=list(SCORING_MODES),
                        help="scoring strategy (default: balanced)")
    parser.add_argument("--profile", default="default",
                        choices=list(PROFILES) + ["all"], help="user profile to run, or 'all'")
    parser.add_argument("-k", type=int, default=5, help="number of recommendations (default 5)")
    parser.add_argument("--no-diversity", action="store_true",
                        help="turn off the artist/genre diversity penalty")
    parser.add_argument("--compare-modes", action="store_true",
                        help="run the chosen profile in every scoring mode")
    parser.add_argument("--diversity-demo", action="store_true",
                        help="show top k with and without the diversity penalty")
    parser.add_argument("--experiment", action="store_true",
                        help="run the energy x2 / genre x0.5 weight-shift experiment")
    parser.add_argument("--list", action="store_true", help="list profiles and modes")
    return parser.parse_args()


def main() -> None:
    """Load the catalog and print recommendations according to the CLI options."""
    args = parse_args()
    songs = load_songs(DATA_PATH)
    print(f"Loaded {len(songs)} songs from {DATA_PATH}")
    diversity = not args.no_diversity
    profile_keys = EVALUATION_ORDER if args.profile == "all" else [args.profile]

    if args.list:
        print("\nProfiles:")
        for key in EVALUATION_ORDER:
            print(f"  {key:<18} {PROFILES[key]['label']}")
        print("\nScoring modes:")
        for mode in SCORING_MODES.values():
            print(f"  {mode.name:<15} {mode.description}")
        return

    if args.compare_modes:
        for key in profile_keys:
            columns = {name: rank_songs(PROFILES[key]["prefs"], songs, k=args.k,
                                        mode=name, diversity=diversity)
                       for name in SCORING_MODES}
            compare_columns(f"{PROFILES[key]['label']}: all scoring modes "
                            f"(diversity {'ON' if diversity else 'OFF'})", columns, args.k)
        return

    if args.diversity_demo:
        for key in profile_keys:
            print_profile(key, songs, args.mode, args.k, diversity=False)
            print_profile(key, songs, args.mode, args.k, diversity=True)
        return

    if args.experiment:
        print(f"\nExperiment: {EXPERIMENT_MODE.description}")
        keys = EVALUATION_ORDER if args.profile in ("default", "all") else profile_keys
        for key in keys:
            columns = {
                "baseline (balanced)": rank_songs(PROFILES[key]["prefs"], songs, k=args.k,
                                                  mode="balanced", diversity=False),
                "energy x2, genre x0.5": rank_songs(PROFILES[key]["prefs"], songs, k=args.k,
                                                    mode=EXPERIMENT_MODE, diversity=False),
            }
            compare_columns(f"{PROFILES[key]['label']} (diversity OFF to isolate weights)",
                            columns, args.k)
        return

    for key in profile_keys:
        print_profile(key, songs, args.mode, args.k, diversity)


if __name__ == "__main__":
    main()
