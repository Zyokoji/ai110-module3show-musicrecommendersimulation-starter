# AI Interactions Log

This file has two parts:
1. **Final project (Applied AI System)**: how VibeMatch 2.0 was built with an AI coding agent, including real workflow traces.
2. **Module 3**: the original log, kept unchanged below.

---

# Part 1: Final project (Applied AI System)

## Who did what

- **Student:** wrote the requirements and constraints for the final project, chose to keep commits local (no push without approval), and asked for honest labelling of rule-based logic and no invented results. **[Personalize: add anything you reviewed, tested or decided yourself.]**
- **AI coding agent (Claude Code in VS Code):** inspected the repository, wrote all new code, data files, tests and documentation, and ran the app, the tests and the evaluation harness to check its work.
- **No external AI service is used *inside* the project.** No API key was available, so every AI feature runs locally (TF-IDF retrieval, rule-based parsing, a fixed workflow).

## Prompt used (excerpts, quoted verbatim)

> "Turn my music recommender into a smarter, more reliable recommendation system that explains its recommendations and evaluates their quality."

> "Integrate at least one meaningful AI feature, such as retrieval, an agentic workflow, or a reliability system. It must affect how recommendations are generated, not just exist as a separate script."

> "If a feature requires an unavailable API key or external service, use a practical local alternative where possible and document any limitations. Do not pretend a rule-based algorithm is a trained AI model."

> "Make multiple meaningful local Git commits as you complete major stages, but do not push to GitHub or change the remote repository without my approval."

This was one long prompt; no other prompts were used for the final-project build.

## Key decisions made during the build

| Decision | Reasoning | Verified by |
|---|---|---|
| Local TF-IDF retrieval instead of an LLM | No API key; deterministic, testable, explainable | Baseline comparison: workflow 16/17 vs baseline 10/17 on quality + edge cases |
| Retrieval changes scores in 3 ways (context preferences, related genres, "matches your words" points) | Requirement: the AI feature must affect recommendations | Example outputs; `test_baseline_skips_retrieval_and_differs` |
| Reuse Module 3 `score_song` / `rank_songs` instead of a new scorer | No duplicated logic; Module 3 behaviour stays the same | The 25 Module 3 tests still pass unchanged |
| Fixed 8-step workflow with a recorded trace | Every decision is visible and testable | `--trace` output (below); `test_workflow_normal_request_with_full_trace` |
| Confidence = top score ÷ best possible score; capped at "medium" for a genre missing from the catalog | Simple, explainable, avoids overclaiming | Case E1 (k-pop) |
| Never recommend songs with a score of 0 | No "recommendation" without a reason | Baseline returning 1–2 songs in the evaluation shows this working |
| Keep the failing case Q12 as a known limitation | Honest evaluation over a perfect score | Brute-force check: 0 of 15,504 five-song sets can meet it |
| Removed unused `pandas` and `streamlit` from requirements | Fewer dependencies; nothing imported them | `grep` found no imports; all tests pass |

## Corrections made after verification

1. **Parser rules (found by reviewing the rules before running).** "love" → romantic and "down" → sad would misread "I love jazz" and "wind down". A 3-word negation window would make "no lofi, just jazz" exclude jazz too. The two words were removed, the window was shortened to 2 words, and a test was added.
2. **Duplicate rejection messages (found by running the CLI).** Rejections were printed twice, once by the logger's console handler and once by the app. The console now shows only errors (INFO with `--verbose`), and everything is still written to the log file.
3. **Wrong test expectation (found by running the tests).** A new test assumed the k-pop request's top 3 would be only pop/edm. With the diversity penalty on, *Rooftop Lights* (indie pop) is #3. The code was right, and the test now checks the top 2.
4. **Evaluation case Q12 failed (found by the harness).** Instead of loosening the expectation, the agent checked all 15,504 five-song combinations, found that none could pass, and labelled the case a known limitation. It still counts as a FAIL.
5. **Inconsistent trace (found by reading a real trace).** For "no lofi, just chill jazz", the trace listed lofi as a *related genre* even though lofi was excluded. The results were not affected (lofi songs are removed in step 5), but the trace contradicted itself. Excluded genres are now filtered out of the related list, and `test_excluded_genre_is_not_offered_as_related_genre` was added.
6. **A claim in the model card was narrowed after checking the data.** "Workout favors pop and edm" became "pop, edm and rock", because the rock song is also fast and high-energy.

## Blocked action

The agent tried to render `diagrams/architecture.mmd` with the Mermaid CLI (`npx @mermaid-js/mermaid-cli`) to check its syntax and save an image to `assets/`. Downloading that package was **denied by the permission system**, and the agent did not try to work around it. The diagram was checked by hand against Mermaid flowchart syntax, and the same diagram is embedded in the README so GitHub renders it.

## Agentic workflow traces (real output)

The workflow is a **fixed** sequence of steps. A language model does not choose the steps, but every intermediate decision is recorded. Two real traces:

**Unknown genre, falling back to related genres:**

```text
$ python -m src.app "k-pop dance hits" -k 3 --trace
Loaded 20 songs and 11 activity contexts.

=== AI workflow (retrieval + self-check) ===
Request    : k-pop dance hits
Context    : party
Using      : energy=0.85, danceability=0.88, valence=0.8, mood_tags=['party', 'euphoric', 'carefree'], related_genres=['pop', 'edm']
Confidence : 0.88 (medium)
Note       : 'k-pop' is not in the catalog; using related genres pop, edm instead.
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Pulse Reactor          | edm          | 4.86         | related genre: edm (+1.00)                                     |
|    | by Max Pulse           | euphoric     |              | mood tags party, euphoric (2/3) (+0.67)                        |
|    |                        |              |              | energy 0.95 vs target 0.85 (90% similar) (+1.35)               |
|    |                        |              |              | valence 0.8 vs target 0.8 (100% similar) (+0.50)               |
|    |                        |              |              | danceability 0.92 vs target 0.88 (96% similar) (+0.48)         |
|    |                        |              |              | matches your words: dance (+0.86)                              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Bubblegum Skies        | pop          | 4.68         | related genre: pop (+1.00)                                     |
|    | by Neon Echo           | happy        |              | mood tags party, carefree (2/3) (+0.67)                        |
|    |                        |              |              | energy 0.85 vs target 0.85 (100% similar) (+1.50)              |
|    |                        |              |              | valence 0.9 vs target 0.8 (90% similar) (+0.45)                |
|    |                        |              |              | danceability 0.84 vs target 0.88 (96% similar) (+0.48)         |
|    |                        |              |              | matches your words: pop (+0.58)                                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Rooftop Lights         | indie pop    | 3.65         | mood tags carefree (1/3) (+0.33)                               |
|    | by Indigo Parade       | happy        |              | energy 0.76 vs target 0.85 (91% similar) (+1.36)               |
|    |                        |              |              | valence 0.81 vs target 0.8 (99% similar) (+0.49)               |
|    |                        |              |              | danceability 0.82 vs target 0.88 (94% similar) (+0.47)         |
|    |                        |              |              | matches your words: pop (+1.00)                                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
Summary:
  1. Pulse Reactor: Top reasons: energy 0.95 vs target 0.85 (90% similar); related genre: edm; matches your words: dance.
  2. Bubblegum Skies: Top reasons: energy 0.85 vs target 0.85 (100% similar); related genre: pop; mood tags party, carefree (2/3).
  3. Rooftop Lights: Top reasons: energy 0.76 vs target 0.85 (91% similar); matches your words: pop; valence 0.81 vs target 0.8 (99% similar).

Workflow trace:
  1. validate     -> request accepted
       query: "k-pop dance hits"
       k: 3
       mode: "balanced"
       diversity: true
  2. parse        -> found 1 explicit preference(s)
       explicit: {"genre": "k-pop"}
       exclude_genres: []
       notes: ["'k-pop' -> genre k-pop (not in catalog)"]
  3. retrieve     -> best context: party
       contexts: [{"name": "party", "score": 0.2887, "matched": ["dance"]}]
       top_song_matches: {"10": {"score": 1.0, "terms": ["pop"]}, "16": {"score": 0.86, "terms": ["dance"]}, "1": {"score": 0.58, "terms": ["pop"]}, "20": {"score": 0.58, "terms": ["pop"]}, "5": {"score": 0.58, "terms": ["pop"]}}
  4. build_prefs  -> 5 preference(s) set
       prefs: {"energy": 0.85, "danceability": 0.88, "valence": 0.8, "mood_tags": ["party", "euphoric", "carefree"], "related_genres": ["pop", "edm"]}
       sources: {"energy": "context 'party'", "danceability": "context 'party'", "valence": "context 'party'", "mood_tags": "context 'party'", "related_genres": "genre notes for k-pop", "retrieval_scores": "song text search"}
  5. constrain    -> no exclusions
       exclude_genres: []
       candidates: 20
  6. rank         -> ranked 20 songs, kept top 3
       top: [["Pulse Reactor", 4.86], ["Bubblegum Skies", 4.68], ["Rooftop Lights", 3.65]]
  7. self_check   -> confidence 0.88 (medium)
       top_score: 4.86
       max_possible: 5.5
       problems: []
  8. explain      -> added a one-line summary to each recommendation
```

**Negated genre, excluded before ranking:**

```text
$ python -m src.app "no lofi, just chill jazz" -k 3 --trace
Loaded 20 songs and 11 activity contexts.

=== AI workflow (retrieval + self-check) ===
Request    : no lofi, just chill jazz
Context    : relax
Using      : energy=0.38, valence=0.6, mood_tags=['calm', 'mellow', 'warm'], genre=jazz, mood=chill, related_genres=['r&b']
Confidence : 0.76 (high)
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Coffee Shop Stories    | jazz         | 5.29         | genre match: jazz (+2.00)                                      |
|    | by Slow Stereo         | relaxed      |              | mood tags mellow, warm (2/3) (+0.67)                           |
|    |                        |              |              | energy 0.37 vs target 0.38 (99% similar) (+1.48)               |
|    |                        |              |              | valence 0.71 vs target 0.6 (89% similar) (+0.45)               |
|    |                        |              |              | matches your words: jazz (+0.69)                               |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Spacewalk Thoughts     | ambient      | 3.51         | mood match: chill (+1.00)                                      |
|    | by Orbit Bloom         | chill        |              | mood tags calm (1/3) (+0.33)                                   |
|    |                        |              |              | energy 0.28 vs target 0.38 (90% similar) (+1.35)               |
|    |                        |              |              | valence 0.65 vs target 0.6 (95% similar) (+0.47)               |
|    |                        |              |              | matches your words: chill (+0.36)                              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Slow Honey             | r&b          | 3.46         | related genre: r&b (+1.00)                                     |
|    | by Amber Lane          | romantic     |              | mood tags mellow, warm (2/3) (+0.67)                           |
|    |                        |              |              | energy 0.5 vs target 0.38 (88% similar) (+1.32)                |
|    |                        |              |              | valence 0.66 vs target 0.6 (94% similar) (+0.47)               |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
Summary:
  1. Coffee Shop Stories: Top reasons: genre match: jazz; energy 0.37 vs target 0.38 (99% similar); matches your words: jazz.
  2. Spacewalk Thoughts: Top reasons: energy 0.28 vs target 0.38 (90% similar); mood match: chill; valence 0.65 vs target 0.6 (95% similar).
  3. Slow Honey: Top reasons: energy 0.5 vs target 0.38 (88% similar); related genre: r&b; mood tags mellow, warm (2/3).

Workflow trace:
  1. validate     -> request accepted
       query: "no lofi, just chill jazz"
       k: 3
       mode: "balanced"
       diversity: true
  2. parse        -> found 2 explicit preference(s)
       explicit: {"genre": "jazz", "mood": "chill"}
       exclude_genres: ["lofi"]
       notes: ["'jazz' -> genre jazz", "'lofi' is negated -> exclude genre lofi", "'chill' -> mood chill"]
  3. retrieve     -> best context: relax
       contexts: [{"name": "relax", "score": 0.25, "matched": ["chill"]}]
       top_song_matches: {"2": {"score": 1.0, "terms": ["chill", "lofi"]}, "4": {"score": 0.91, "terms": ["chill", "lofi"]}, "19": {"score": 0.86, "terms": ["chill", "lofi"]}, "7": {"score": 0.69, "terms": ["jazz"]}, "9": {"score": 0.43, "terms": ["lofi"]}}
  4. build_prefs  -> 6 preference(s) set
       prefs: {"energy": 0.38, "valence": 0.6, "mood_tags": ["calm", "mellow", "warm"], "genre": "jazz", "mood": "chill", "related_genres": ["r&b"]}
       sources: {"energy": "context 'relax'", "valence": "context 'relax'", "mood_tags": "context 'relax'", "genre": "your words", "mood": "your words", "related_genres": "genre notes for jazz", "retrieval_scores": "song text search"}
  5. constrain    -> removed 4 song(s) from excluded genres
       exclude_genres: ["lofi"]
       candidates: 16
  6. rank         -> ranked 16 songs, kept top 3
       top: [["Coffee Shop Stories", 5.29], ["Spacewalk Thoughts", 3.51], ["Slow Honey", 3.46]]
  7. self_check   -> confidence 0.76 (high)
       top_score: 5.29
       max_possible: 7.0
       problems: []
  8. explain      -> added a one-line summary to each recommendation
```

---

# Part 2: Module 3 log (original)

This log describes the real workflow used to complete the project with an AI coding agent (**Claude Code**, running in VS Code). All of the work below happened in one agent conversation. Unless a line says otherwise, the code, tests, data and documentation were **generated by the agent**, and the checks listed were **run by the agent** (tests, program runs, scripts). Anything the student checked or decided personally should be added in the marked spot at the end.

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

Follow-up requests in the same conversation:

- A one-line request to push to the student's own repository: *"push to https://github.com/Zyokoji/ai110-module3show-musicrecommendersimulation-starter"* (verbatim).
- A request to finish the reflection sections, make this log complete and accurate, and check the final documentation. It explicitly said not to change the recommendation logic or dataset.

No other prompts were used. The excerpts above are copied from the actual messages, not reconstructed.

**How the scoring logic was developed**

1. The agent read the starter files first: 10 songs, all functions stubbed, and a starter scoring idea of genre +2.0, mood +1.0 and energy closeness.
2. It kept those three weights as the `balanced` mode and added smaller weights (0.25–1.0) for the other features, so they act as tie-breakers.
3. Numeric features use `similarity = 1 − |song − target| ÷ range`, so being *close* to the target earns points. Higher or lower values earn nothing by themselves. Tempo uses a 120 BPM range and popularity a 100-point range.
4. Each point value is rounded before adding, so the reasons printed for a song always add up to its score.
5. Ranking was built separately from scoring. `score_song` scores one song. `rank_songs` scores all of them, sorts them with `sorted()`, and keeps the top k.

**What did the agent generate or change?**

| File | Change |
|---|---|
| `data/songs.csv` | Kept the 10 starter songs. Added 10 new songs (hip hop, classical, country, metal, r&b, edm, folk, reggae, one more lofi and one more pop) and 5 new columns: `popularity`, `release_decade`, `instrumentalness`, `liveness`, `mood_tags`. All values are simulated, with fictional artists. |
| `src/recommender.py` | Implemented `load_songs` (csv module, int/float conversion, range checks, reported skips), `score_song` (genre/mood/tags/closeness/decade with reasons), `rank_songs` (sorting plus greedy diversity re-ranking), `recommend_songs`, the `ScoringMode` strategy objects, and the `Recommender` OOP class. Extended the `Song` and `UserProfile` dataclasses. |
| `src/main.py` | Fixed the starter import (`from recommender import` failed under `python -m src.main`). Added 7 profiles, a plain-Python ASCII table, and the CLI flags `--mode`, `--profile`, `-k`, `--no-diversity`, `--compare-modes`, `--diversity-demo`, `--experiment` and `--list`. |
| `tests/test_scoring.py` | 23 new tests (on top of the 2 starter tests). |
| `README.md`, `model_card.md` | Full documentation. Every terminal output block was produced by running the program and inserted by a small script, not typed by hand. |

Commands the agent ran included `python -m src.main` with every flag, `python -m pytest`, scripts that computed dataset statistics (genre, mood and energy counts) and top-5 overlaps between profiles, and `git status` / `git commit`.

**How the project was tested**

- `python -m pytest`: the 2 starter tests plus 23 new ones in `tests/test_scoring.py` (25 total, all passing). They cover CSV loading and types, invalid or missing rows, genre/mood matching, numeric closeness, "score = sum of reasons", ordering and top-k, the scoring modes, the diversity penalty, and 6 CLI commands run as subprocesses.
- Manual program runs: every CLI flag was run, and the output was compared with what the docs say.
- Small scripts computed the dataset counts (genres, moods, energy ranges) and the top-5 overlap between every pair of profiles before those numbers were written into the model card.

**What did you verify or fix?** *(checks and corrections made by the agent during the session)*

- **A wrong test assumption was caught by running the code.** The agent first wrote a test claiming `energy-focused` mode would put a non-pop song at #1 for the High-Energy Pop profile. The test failed, because *Gym Hero* (pop, intense, energy 0.93) wins in every mode. The agent printed the real mode comparison and rewrote the test to check behavior the program actually showed (the conflicting "sad but high-energy" profile flips its #1 between `genre-first` and `energy-focused`).
- **Score consistency:** rounding each point value before adding it guarantees that the reasons add up exactly to the displayed score. A test checks this for every song.
- **Documentation claims were checked against output.** Profile overlaps, dataset counts and experiment results were computed with scripts before being written down. One draft comparison sentence ("~65–70% similarity") was wrong when checked and was rewritten.
- **Finding noticed during verification:** `genre-first` gives the same order as `balanced` when a profile has no genre match. This is documented as a limitation rather than hidden.
- **Starter issues found:** the broken `main.py` import, and an unclosed code fence in the README setup section.
- **Push decision:** at first, `origin` pointed at the upstream `codepath/...-starter` repository, so the agent committed locally and did not push. After the student asked to push to their own repository, the agent renamed the CodePath remote to `upstream`, set `origin` to the student's repository and pushed `main`.

**AI-generated work vs. verification**

| Generated by the AI agent | How it was verified |
|---|---|
| `load_songs`, `score_song`, `rank_songs`, `recommend_songs`, `Recommender` | 25 pytest tests; real program runs |
| 10 new songs and 5 new columns (simulated values) | load test checks types and ranges for every row; counts computed by script |
| Scoring modes and diversity penalty | tests confirm modes differ and change rankings, and the penalty uses already-selected songs; `--compare-modes` and `--diversity-demo` runs |
| README / model card text and evaluation findings | output blocks inserted by script from real runs; numbers and overlaps re-computed by script |
| Reflection text | written from the project results; personal parts are marked for the student |

**Student's own decisions (from the conversation):**

- Set the requirements and rules in the master prompt: complete every phase and all four challenges, use only real program output, label generated data as simulated, and don't invent personal reflections.
- Chose to push the project to their own repository (`Zyokoji/...`) rather than the CodePath starter.
- Asked for the reflection and this log to keep AI-generated work separate from verification, and to mark personal details instead of inventing them.
- Planned to review the final answers after the agent finished.

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

The diversity step is a greedy re-ranking in `rank_songs(..., diversity=True)`. Each round, every remaining song's penalty is computed from the songs **already selected** (`_diversity_penalty`): −1.0 per same-artist song and −0.5 per same-genre song. The song with the best `base − penalty` is picked. The base score, penalty and final score are all kept and shown in the table. Songs with a blank artist are never counted as an artist repeat.

Verification: `test_diversity_penalty_uses_already_selected_songs`, `test_missing_artist_is_not_treated_as_repeat` and `test_diversity_reduces_repeated_artists_on_real_data`. On the real data, Chill Lofi went from 4 lofi songs (3 by LoRoom) to 3 lofi songs (2 by LoRoom) plus an ambient and a folk song.

---

## Visual Summary Table (Challenge 4)

`tabulate` was not installed, so the agent wrote a small `format_table()` helper in `src/main.py` using plain Python (`textwrap` plus string padding). Each row shows the rank, title and artist, genre and mood, final score (with the base score when a penalty applied) and **every** scoring reason. The header line above each table shows the scoring mode, whether diversity is on, and k. The CLI tests run each command, and real table output is pasted into the README and model card.
