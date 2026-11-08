# AI Interactions Log

This log describes the real workflow used to complete the project with an AI coding agent (**Claude Code**, running in VS Code). Everything below happened in a single agent session. The student should add any personal notes, prompts or extra checks they did themselves.

---

## Agentic Workflow (SF8)

**What task did you give the agent?**

Complete the whole Music Recommender Simulation (Phases 1–5) plus all four optional challenges: advanced song features, multiple scoring modes, diversity penalty and visual summary table. Then test, document and commit it.

**Prompts used:**

The task was given as one long "master prompt." Key excerpts (quoted from the actual prompt):

> "Your mission is to complete EVERY requirement in the project instructions, from Phase 1 through Phase 5, INCLUDING ALL FOUR OPTIONAL EXTENSION CHALLENGES."

> "Do not invent results, evaluation findings, terminal outputs, or personal reflections. Run the program and use actual results."

> "Introduce at least FIVE new complex attributes … For generated song data, do not invent real-world artist identities or factual popularity measurements. Clearly identify generated data as simulated."

> "Implement at least TWO different scoring and ranking strategies … Use an appropriate design pattern, such as a simple Strategy pattern, if useful."

> "The diversity logic must be based on the recommendations already selected."

**What did the agent generate or change?**

| File | Change |
|---|---|
| `data/songs.csv` | Kept the 10 starter songs. Added 10 new songs (hip hop, classical, country, metal, r&b, edm, folk, reggae, one more lofi and one more pop) and 5 new columns: `popularity`, `release_decade`, `instrumentalness`, `liveness`, `mood_tags`. All values are simulated, with fictional artists. |
| `src/recommender.py` | Implemented `load_songs` (csv module, int/float conversion, range checks, reported skips), `score_song` (genre/mood/tags/closeness/decade with reasons), `rank_songs` (sorting plus greedy diversity re-ranking), `recommend_songs`, the `ScoringMode` strategy objects, and the `Recommender` OOP class. Extended the `Song` and `UserProfile` dataclasses. |
| `src/main.py` | Fixed the starter import (`from recommender import` failed under `python -m src.main`). Added 7 profiles, a plain-Python ASCII table, and the CLI flags `--mode`, `--profile`, `-k`, `--no-diversity`, `--compare-modes`, `--diversity-demo`, `--experiment` and `--list`. |
| `tests/test_scoring.py` | 23 new tests (on top of the 2 starter tests). |
| `README.md`, `model_card.md` | Full documentation. Every terminal output block was produced by running the program and inserted by a small script, not typed by hand. |

Commands the agent ran included `python -m src.main` with every flag, `python -m pytest`, scripts that computed dataset statistics (genre, mood and energy counts) and top-5 overlaps between profiles, and `git status` / `git commit`.

**What did you verify or fix manually?** *(agent's own checks and corrections; the student should add theirs)*

- **A wrong test assumption was caught by running the code.** The agent first wrote a test claiming `energy-focused` mode would put a non-pop song at #1 for the High-Energy Pop profile. The test failed, because *Gym Hero* (pop, intense, energy 0.93) wins in every mode. The agent printed the real mode comparison and rewrote the test to check behavior the program actually showed (the conflicting "sad but high-energy" profile flips its #1 between `genre-first` and `energy-focused`).
- **Score consistency:** rounding each point value before adding it guarantees that the reasons add up exactly to the displayed score. A test checks this for every song.
- **Documentation claims were checked against output.** Profile overlaps, dataset counts and experiment results were computed with scripts before being written down. One draft comparison sentence ("~65–70% similarity") was wrong when checked and was rewritten.
- **Finding noticed during verification:** `genre-first` gives the same order as `balanced` when a profile has no genre match. This is documented as a limitation rather than hidden.
- **Starter issues found:** the broken `main.py` import, and an unclosed code fence in the README setup section.
- **Push decision:** `origin` points at the upstream `codepath/...-starter` repository, not a personal fork, so the agent committed locally and did not push to it (see the final report).

---

## Advanced Features (Challenge 1)

| New attribute | Type | How it affects recommendations |
|---|---|---|
| `popularity` | int 0–100 | Closeness to the user's `popularity` target (range 100). Weight 0.25 in balanced mode. |
| `release_decade` | int | +0.5 for the same decade, +0.25 for a neighbouring decade. |
| `instrumentalness` | float 0–1 | Closeness to target (weight 0.5). The Chill Lofi profile targets 0.9 for vocal-free study music. |
| `liveness` | float 0–1 | Closeness to target (weight 0.25). The Rock profile targets 0.3 for a slight live feel. |
| `mood_tags` | list of text | Up to +1.0 in balanced mode (+2.0 in mood-first) for the share of the user's tags the song has. |

Verification: `test_advanced_features_change_the_score` checks that each new feature adds points. In the real output, the mood tags decide the Happy Pop #1 vs #2 (*Sunrise City* 3/3 tags vs *Bubblegum Skies* 2/3), and the decade adds another 0.25 gap.

---

## Design Pattern (SF10)

**Which design pattern did you use?**

A simple **Strategy pattern** for the scoring modes.

**How did AI help you brainstorm or implement it?**

The agent considered two designs:

1. **A class per mode** (`GenreFirstScorer`, `MoodFirstScorer`, …), each with its own `score()` method. This is flexible, but it repeats the genre, mood and closeness logic four times, and the modes could drift apart by accident.
2. **One scoring function plus interchangeable weight sets.** Each mode is a `ScoringMode(name, description, weights)` object, and `score_song` runs the same steps with whichever weights it is given.

It chose option 2. The modes differ only in what they emphasize, not in how features are compared, so swapping the weights *is* swapping the strategy. This keeps the code short for a beginner and makes it impossible for two modes to compute "genre match" differently. A test (`test_modes_have_different_weights_and_unknown_mode_fails`) confirms that no two modes share identical weights, and `test_modes_change_rankings` confirms the modes produce different rankings.

**How does the pattern appear in your final code?**

- `ScoringMode` dataclass and the `SCORING_MODES` dictionary in `src/recommender.py`.
- `get_mode()` turns a mode name (or a custom `ScoringMode`) into the strategy.
- `score_song(user_prefs, song, mode=...)` and `rank_songs(..., mode=...)` accept any strategy.
- `src/main.py` passes `--mode` straight through, and the weight-shift experiment is just one more `ScoringMode` (`EXPERIMENT_MODE`). No new scoring code was needed for it.

---

## Diversity Logic (Challenge 3)

The diversity step is a greedy re-ranking in `rank_songs(..., diversity=True)`. Each round, every remaining song's penalty is computed from the songs **already selected** (`_diversity_penalty`): −1.0 per same-artist song and −0.5 per same-genre song. The song with the best `base − penalty` is picked. The base score, penalty and final score are all kept and shown in the table.
