# 🎧 Model Card: VibeMatch 2.0 (Applied AI System)

> The Module 3 model card (scoring rules, profile evaluation, weight experiment) is kept at [docs/module3/model_card.md](docs/module3/model_card.md). This card covers the final-project system.

## 1. System overview

| | |
|---|---|
| **Name** | VibeMatch 2.0 |
| **Task** | Turn a plain-English music request into a ranked, explained list of songs from a small catalog. |
| **Type** | Content-based recommender with **TF-IDF retrieval** over a custom knowledge base, a **rule-based** query parser, and a **fixed 8-step workflow** with self-checks. |
| **Not** | Not a trained machine-learning model, not a large language model, no external API. The scoring weights and knowledge-base values were written by hand. |
| **Inputs** | One request (max 300 characters), the number of songs `k` (1–20), a scoring mode, and diversity on/off. |
| **Outputs** | Up to `k` songs with points per reason, a one-line summary, a confidence score (0–1 with a high/medium/low label), warnings, and an optional decision trace. |
| **Data** | `data/songs.csv` (20 simulated songs, 15 attributes), `data/genre_notes.json` (20 genres: 15 in the catalog, 5 not), `data/activity_contexts.json` (11 listening situations). All of it was written for this class project. |

**Intended use:** classroom demonstration and portfolio. It shows how retrieval, guardrails and evaluation make a simple recommender more reliable and explainable.

**Not intended for:**
- real users or products;
- judging real artists (all artists and popularity values are fictional);
- inferring anything about a person's mental health or identity;
- any decision with consequences.

---

## 2. Limitations and biases

- **Tiny, uneven catalog.** 20 songs; 11 of 15 genres have a single song, while lofi has 4 and pop has 3. Retrieval can find *related* songs but can't create missing ones. The evaluation case "angry music to vent" fails because no 5-song set in the catalog is both high-energy and low-valence on average (checked by brute force).
- **The knowledge base encodes the author's assumptions.** Each activity context is a guess. For example, "sad" means low valence and *acoustic*, so sad requests lean toward folk and classical. "Workout" means fast and high-energy (135 BPM), which favors pop, edm and rock over slower styles. "Dinner" means warm and acoustic. Someone whose sad music is loud metal is poorly served. Genre relationships (rock → metal, k-pop → pop/edm) are also simplified opinions.
- **Word-based understanding.** The parser and TF-IDF match words after light stemming. Synonyms not in the lists ("tranquil", "bops"), misspellings, slang, sarcasm and non-English requests are mostly missed. A request with none of the known words is rejected (`no_preferences`).
- **Popularity and other values are invented.** Popularity is only a small tie-breaker (0.25), but it still reflects made-up numbers.
- **Confidence can sound stronger than it is.** "0.98 (high)" means the top song fits the *stated* preferences well. It does not mean a real listener would like it. The average confidence in the evaluation was 0.92, partly because the system grades itself against the preferences it built.
- **Filter-bubble risk.** Content-based scoring keeps recommending "more of the same". The diversity penalty reduces repeats of the same artist or genre but doesn't introduce unfamiliar styles.

---

## 3. Potential misuse and prevention

| Possible misuse | Prevention in this project |
|---|---|
| Treating mood requests as a mental-health signal, or profiling users | The system never stores profiles or labels users. Crisis language triggers only a short supportive note with the 988 lifeline, never a diagnosis. The card states this use is out of scope. |
| Someone in crisis receiving only sad songs | The wellbeing note is shown along with the results (guardrail tested in evaluation case E4). |
| Prompt-injection-style input ("ignore previous instructions…") | There is no LLM, so text can't change behaviour. The guardrail tells the user it was treated as plain words (case E3). |
| Very long or junk input slowing the system or producing nonsense | 300-character limit, words required, `k` capped at 20. Each is a clear rejection with a code. |
| Presenting simulated data as real facts about artists | Every data file and doc says the data is simulated and the artists are fictional. |
| Privacy of logged requests | Requests are logged to a **local** file (`logs/vibematch.log`), which is excluded from git. A real deployment should anonymize or shorten logs and tell users what is stored. |
| Hiding weak results behind confident output | The confidence score, the "not in the catalog" warning (confidence capped at medium) and the "low confidence" warning make weak matches visible. Lists can be shorter than `k` rather than padded with zero-score songs. |

---

## 4. Reliability testing observations

Results come from real runs, recorded in the README.

- **Automated tests:** 68 pytest tests pass: 25 from Module 3 (unchanged behaviour) and 43 new ones covering the parser, retrieval, guardrails, workflow, CLI and harness.
- **Evaluation harness:** 24 predefined cases. **The workflow passed 23/24**: 11/12 quality, 5/5 edge and 7/7 guardrail. **The keyword-only baseline passed 10/17** quality and edge cases (6/12 quality, 4/5 edge).
- **Where the baseline fails:**
  - It rejects activity-only requests ("music for sleeping", "party music", "yoga and meditation").
  - It returns too few songs ("country songs for a road trip" gave 1, because without context most songs score 0).
  - It finds nothing for "k-pop".
- **The one workflow failure (Q12)** is a catalog limitation, proven by brute force over all 15,504 five-song sets. It is kept as a documented failure rather than loosening the expectation.
- **Determinism:** the same request always gives the same output, because there is no randomness. That made tests stable and failures reproducible.
- **Graceful degradation:** with missing or broken knowledge files, the app still runs. Catalog genres are still recognised, and retrieval for that source is skipped (tested).
- **Observed surprise:** with the diversity penalty on, the k-pop request's #3 became *Rooftop Lights* (indie pop), because the second pop song was penalized. A test that assumed only pop/edm songs in the top 3 failed and was corrected to check the top 2.

---

## 5. How AI was used during development

The project was built with an AI coding agent (**Claude Code**, in VS Code), working from the student's written requirements.

- **The agent generated** the code (`retrieval.py`, `query_parser.py`, `guardrails.py`, `workflow.py`, `app.py`, `logging_setup.py`, the evaluation harness), the knowledge-base JSON files, the tests and these documents.
- **The agent verified** its work by running the app, the 68 tests and the evaluation harness, and by brute-force checking the claim about Q12. Every output block in the README was inserted by a script from real runs.
- **The student** set the requirements and constraints: no invented results, honest labelling of rule-based logic, local commits only and no push without approval. **[Personalize: add anything you reviewed, tested or changed yourself.]**

Details and traces are in [ai_interactions.md](ai_interactions.md).

### One AI suggestion kept in the final design

**Use local TF-IDF retrieval over a hand-written knowledge base instead of an LLM API.** The agent proposed this because no API key was available. It is also deterministic (tests are stable), free, fast and easy to explain in a presentation. It was kept because the baseline comparison showed it made a measurable difference: 16/17 vs 10/17 on quality and edge cases. *(This was the agent's decision under the requirement "use a practical local alternative"; the student should confirm they agree.)*

### One AI suggestion modified after checking

**The first version of the query parser had rules that misread normal requests.**
- The mood list mapped "love" → romantic and "down" → sad, so "I love jazz" would have become a romantic request and "wind down" a sad one.
- The negation rule looked 3 words back, so "no lofi, just jazz" would have excluded jazz as well as lofi.

These were found when the agent reviewed its own rules. "love" and "down" were removed, and the negation window was shortened to 2 words. A test (`test_parser_negation_creates_exclusion_without_hiding_next_genre`) now locks in the corrected behaviour.

A second example of verification changing AI-written work: the agent's first expectation for evaluation case Q12 failed. It was kept unchanged, and the case was labelled a known limitation only after a brute-force check proved it impossible to meet.

---

## 6. Ideas for improvement

1. **Better language understanding:** add a synonym list, or small local word embeddings, so "tranquil" matches "calm". An LLM could be optional, behind a guardrail, when an API key is available.
2. **A larger, balanced catalog** with real, licensed audio features, so retrieval has more to choose from.
3. **Feedback loop:** like/skip buttons that adjust context targets, which would be a first step toward collaborative signals.
4. **Calibrated confidence:** compare the confidence score with real user ratings so "high" means something outside the system's own rules.
