# Presentation outline: VibeMatch (5–7 minutes)

**Setup before presenting:** open a terminal in the project folder and run `python -m pytest -q` once, so the demo starts warm. Have the README architecture diagram open in a browser tab (GitHub renders it).

---

## 1. Hook and problem (0:00–0:45)

- "In Module 3 I built a music recommender. It worked, but to use it you had to write a Python dictionary."
- Show one line of the old way: `{"genre": "pop", "mood": "happy", "energy": 0.8}`.
- Three problems it had:
  - no plain-English input;
  - unknown genres silently gave bad results;
  - no way to check whether results were good.
- Goal for the final project: **smarter, more reliable, explainable, and evaluated.**

## 2. Demo walkthrough (0:45–3:15)

Run these live, in this order:

1. **Normal request:** `python -m src.app "calm lofi for studying" -k 3`
   - Point at the *Context: study* line. Retrieval found the study context and filled in instrumentalness, tempo and mood tags.
   - Point at the reasons column and the `matches your words` line: every point is explained.
2. **Trace:** `python -m src.app "intense rock for the gym" -k 3 --trace`
   - Walk through the 8 steps quickly.
   - Highlight step 4: related genres (metal) give *Iron Cathedral* partial credit. In Module 3 it got nothing.
3. **Honest fallback + baseline:** `python -m src.app "k-pop dance hits" --compare`
   - "k-pop isn't in my catalog. The system says so, uses related genres, and caps confidence at medium."
   - The baseline column is empty: keywords alone found nothing.
4. **Guardrails:** `python -m src.app "!!! ???"` → rejected with a code.
   - Optional: `python -m src.app "sad songs because I want to die" -k 2` shows the wellbeing note.

## 3. Architecture (3:15–4:30)

- Show the Mermaid diagram (README or `diagrams/architecture.mmd`).
- **The 8 steps:** validate → parse → retrieve → build_prefs → constrain → rank → self_check → explain.
- **What the AI part is:** TF-IDF retrieval written in plain Python, searching 3 sources:
  - activity contexts,
  - genre notes,
  - song text enriched with genre descriptions.
- **Be clear:** no LLM, no trained model, no API key. These are classic local techniques, so the system is deterministic and testable.
- Key design choice: retrieval **changes the scores**. It is part of the recommendation logic, not a side feature.

## 4. Testing and evaluation results (4:30–5:45)

- Run `python -m evaluation.run_eval --quiet` (or show the chart `assets/eval_results.svg`).
- Numbers to say. Before presenting, check them against the latest run in the README:
  - **68 pytest tests pass.**
  - **Workflow: 23/24** evaluation cases.
  - **Baseline: 10/17** quality and edge cases (workflow: 16/17).
- The baseline can't handle "music for sleeping" or "party music" at all.
- **The one failure:** "angry music to vent". I proved it can't pass with this catalog (0 of 15,504 five-song sets work), so I kept it as a documented limitation instead of changing the test to pass.

## 5. Lessons learned and limitations (5:45–6:45)

- Retrieval helped more than any weight change in Module 3.
- Tests caught wrong *expectations* as well as wrong code (the k-pop diversity case).
- Limitations:
  - a tiny simulated catalog;
  - word-based understanding (no synonyms or typos);
  - knowledge-base numbers are my guesses.
- Next steps: a synonym list or small embeddings, a bigger real catalog, like/skip feedback.
- **[Personalize: one sentence on what you personally learned or would do differently.]**

## 6. Close (6:45–7:00)

- "VibeMatch turns a sentence into explained recommendations, tells you when it isn't confident, and has an evaluation that reports its own failures."
- Invite questions.

---

### Backup answers for likely questions

- **"Is this really AI?"** The AI parts are retrieval (TF-IDF, an information-retrieval technique) and an automated multi-step decision workflow with self-checks. There is no machine-learning model; I say that in the README and the model card.
- **"Why not use ChatGPT/Claude?"** No API key was required for the project. A local approach is free, deterministic and testable. An LLM could be added later behind the same guardrails.
- **"How do you know it's better?"** The baseline comparison on 17 predefined cases: 16 vs 10.
- **"What would break it?"** Synonyms it doesn't know ("tranquil"), misspellings, and genres or moods the catalog doesn't have.
