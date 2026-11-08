# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatch 1.0**: a CLI-first, content-based music recommender with switchable scoring modes and a diversity penalty.

---

## 2. Goal / Task

VibeMatch suggests the **top k songs** (default 5) from a small catalog for one user. The user describes their taste: a favorite genre and mood, target values for energy and other features, and optional mood tags and an era.

It does not predict ratings or learn from behavior. It ranks songs by how closely they match the stated preferences, and it explains every point.

---

## 3. Data Used

- **20 songs** in `data/songs.csv`: the 10 starter songs (kept unchanged) plus 10 added songs.
- **15 columns:** `id, title, artist, genre, mood, energy, tempo_bpm, valence, danceability, acousticness` (the original columns) plus 5 advanced columns added for Challenge 1: `popularity` (0–100), `release_decade`, `instrumentalness` (0–1), `liveness` (0–1) and `mood_tags` (several tags separated by `;`).
- **15 genres** and **13 moods.** Counts from the actual file:
  - Genres: lofi 4, pop 3, and 1 song each for rock, ambient, jazz, synthwave, indie pop, hip hop, classical, country, metal, r&b, edm, folk and reggae.
  - Moods: chill 4, happy 3, intense 2, relaxed 2, and 1 each for the other 9.
  - Artists: Neon Echo 3 songs, LoRoom 3, Max Pulse 2, everyone else 1.
  - Energy: 8 songs below 0.45, only 3 between 0.45 and 0.70, and 9 at 0.70 or above (range 0.22–0.97).
  - Decades: 2010s 6, 2020s 6, 2000s 3, 1990s 3, 1980s 1, 1970s 1.
- **All data is simulated.** The artists are fictional, and popularity, decade and mood tags were invented for this exercise. They are not real chart or streaming numbers.
- I deliberately gave some artists several songs (Neon Echo, LoRoom) so the diversity penalty could be tested. *Rainy Window Beats* is intentionally a close cousin of *Library Rain*.
- **Missing from the data:** lyrics, language, region, instruments, any user listening history, and most of the world's genres.

---

## 4. Algorithm Summary

In plain language, every song starts at 0 points and earns points like this (default **balanced** mode):

- **Same genre** as the user: +2.0. **Same mood:** +1.0. Upper/lower case and extra spaces are ignored.
- **Mood tags:** up to +1.0, based on how many of the user's tags the song also has.
- **Numbers** (energy, valence, danceability, acousticness, instrumentalness, liveness, tempo, popularity): the closer the song is to the user's target, the more points. A perfect match on energy is worth +1.5. The other numbers are worth +0.25 to +0.5. Being far away earns ~0 and never subtracts points.
- **Decade:** +0.5 for the same decade, +0.25 for the decade next to it.
- Add it all up to get the **base score**. The highest scores win.

Other parts of the system:

- **Scoring modes (Challenge 2):** the same rules with different weights. `genre-first` (genre +4.0), `mood-first` (mood +3.0, tags +2.0), `energy-focused` (energy +4.0, tempo/danceability +1.0). Each is a `ScoringMode` "strategy" object.
- **Diversity penalty (Challenge 3):** while filling the top 5, a song loses 1.0 point for each already-picked song by the same artist and 0.5 for each already-picked song in the same genre. **Final ranking score = base score − penalty.** The base score is still shown. Songs with no artist are never penalized as an artist repeat.
- **Changes from the starter logic:** the starter idea was genre +2, mood +1 and energy closeness. I kept those weights in balanced mode and added smaller weights for the other features, the mood tags, the decade, the modes and the diversity step.

---

## 5. Observed Behavior / Biases

### Strengths

- Clear profiles get intuitive #1 picks. *Sunrise City* for happy pop, *Gym Hero* for high-energy pop, *Library Rain* for chill lofi, *Storm Runner* for intense rock.
- Every score can be checked by hand: the reasons add up exactly to the total (a test enforces this).
- Messy input is handled: `" HAPPY "` still matches `happy`.
- Closeness scoring works in both directions. The low-energy boundary profile gets the calmest songs, not the "biggest" values.

### Limitations and Bias

The catalog has 15 genres, but 11 of them have exactly one song. A rock, metal, folk or classical fan gets one real genre match and then four "filler" songs chosen only by energy and other numbers: the Deep Intense Rock profile received an indie pop song (*Rooftop Lights*) and a hip hop song (*Concrete Poetry*) at #4 and #5. Lofi (4 songs, 3 by LoRoom) and pop (3 songs, 2 by Neon Echo) are over-represented, so those listeners see near-identical picks unless the diversity penalty is on. Genre and mood are exact text matches worth 3 of roughly 9 possible points in balanced mode, so "indie pop" earns nothing for a "pop" fan, and a user whose genre is not in the catalog ("k-pop") can never score above 2.5. The energy values form two clusters (8 songs below 0.45, 9 at 0.70 or above, only 3 in between), so a mid-energy listener gets weaker closeness matches than someone at either extreme. Finally, popularity, decade and mood tags were invented for this simulation, so the system reflects the dataset author's assumptions about music rather than real listener behavior.

### Other observed patterns

- **Filter bubble:** without the diversity penalty, Chill Lofi's top 5 had 4 lofi songs, 3 of them by LoRoom. Content-based scoring keeps returning "more of the same."
- **Label beats feel:** in balanced mode, genre + mood (3.0 points) beat a perfect energy match (1.5). The "sad but high-energy" user gets a quiet folk song first.
- **Mode collapse:** when no song matches the user's genre, `genre-first` produces exactly the same order as `balanced`, just with all scores halved. The extra genre weight has nothing to act on.

---

## 6. Evaluation Process

### Profiles tested

| Key | Profile | What it tests |
|---|---|---|
| `default` | Happy Pop (pop, happy, energy 0.8, tags uplifting/sunny/carefree, 2010s) | the CLI default |
| `high-energy-pop` | pop, intense, energy 0.92, tempo 130, tags pumped/party, 2020s | normal listener #1 |
| `chill-lofi` | lofi, chill, energy 0.35, acoustic 0.8, instrumental 0.9, tempo 75, tags calm/study/rainy | normal listener #2 |
| `deep-intense-rock` | rock, intense, energy 0.9, valence 0.4, tempo 150, tags aggressive/adrenaline, 2000s | normal listener #3 |
| `sad-but-hyper` | folk, sad, **energy 0.95**, valence 0.1, tempo 160 | adversarial: conflicting preferences |
| `boundary-silence` | energy 0.0, valence 0.0, danceability 0.0, acousticness 1.0, instrumentalness 1.0; **no genre/mood** | edge: boundary values, missing preferences |
| `ghost-genre` | genre **"k-pop"** (not in catalog), mood **" HAPPY "** (messy casing), energy 0.6 | edge: unknown/unusual input |

I ran `python -m src.main --profile all` (balanced mode, diversity ON, top 5). I looked at whether the #1 song fit the profile, why each song earned its points, which songs repeated across profiles, and what happened with the edge cases. I also ran `--compare-modes`, `--diversity-demo` and `--experiment`, plus 25 automated tests.

### Top 5 for each profile (summary of the real output below)

| Profile | #1 | #2 | #3 | #4 | #5 |
|---|---|---|---|---|---|
| Default Happy Pop | Sunrise City 7.67 | Bubblegum Skies 5.46 (base 6.96) | Rooftop Lights 5.26 | Gym Hero 4.39 (base 5.39) | Concrete Poetry 3.56 |
| High-Energy Pop | Gym Hero 6.44 | Bubblegum Skies 5.10 (base 5.60) | Storm Runner 3.51 | Pulse Reactor 3.16 (base 4.16) | Sunrise City 2.76 (base 4.76) |
| Chill Lofi | Library Rain 7.45 | Rainy Window Beats 6.94 (base 7.44) | Midnight Coding 5.00 (base 7.00) | Spacewalk Thoughts 4.34 | Paper Boats 3.10 |
| Deep Intense Rock | Storm Runner 7.18 | Gym Hero 4.18 | Iron Cathedral 3.71 | Rooftop Lights 2.46 | Concrete Poetry 2.45 |
| Sad but Hyper | Paper Boats 4.09 | Iron Cathedral 2.36 | Storm Runner 2.22 | Pulse Reactor 2.02 | Bubblegum Skies 1.79 |
| Boundary Silence | Moonlit Sonata Redux 2.89 | Spacewalk Thoughts 2.48 | Library Rain 2.28 | Paper Boats 2.26 | Coffee Shop Stories 2.13 |
| Ghost Genre (k-pop) | Rooftop Lights 2.26 | Sunrise City 2.17 | Island Time 1.47 | Dusty Backroads 1.43 | Slow Honey 1.35 |

<details>
<summary><b>Full terminal output: <code>python -m src.main --profile all</code></b> (click to expand)</summary>

```text
$ python -m src.main --profile all
Loaded 20 songs from data/songs.csv

=== Profile: Default: Happy Pop ===
Preferences : genre=pop, mood=happy, energy=0.8, valence=0.8, danceability=0.8, likes_acoustic=False, mood_tags=['uplifting', 'sunny', 'carefree'], popularity=75, release_decade=2010
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Sunrise City           | pop          | 7.67         | genre match: pop (+2.00)                                       |
|    | by Neon Echo           | happy        |              | mood match: happy (+1.00)                                      |
|    |                        |              |              | mood tags uplifting, sunny, carefree (3/3) (+1.00)             |
|    |                        |              |              | energy 0.82 vs target 0.8 (98% similar) (+1.47)                |
|    |                        |              |              | valence 0.84 vs target 0.8 (96% similar) (+0.48)               |
|    |                        |              |              | danceability 0.79 vs target 0.8 (99% similar) (+0.49)          |
|    |                        |              |              | popularity 78 vs target 75 (97% similar) (+0.24)               |
|    |                        |              |              | acousticness 0.18 vs target 0.2 (98% similar) (+0.49)          |
|    |                        |              |              | from the 2010s (+0.50)                                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Bubblegum Skies        | pop          | 5.46         | genre match: pop (+2.00)                                       |
|    | by Neon Echo           | happy        | (base 6.96)  | mood match: happy (+1.00)                                      |
|    |                        |              |              | mood tags sunny, carefree (2/3) (+0.67)                        |
|    |                        |              |              | energy 0.85 vs target 0.8 (95% similar) (+1.43)                |
|    |                        |              |              | valence 0.9 vs target 0.8 (90% similar) (+0.45)                |
|    |                        |              |              | danceability 0.84 vs target 0.8 (96% similar) (+0.48)          |
|    |                        |              |              | popularity 85 vs target 75 (90% similar) (+0.23)               |
|    |                        |              |              | acousticness 0.1 vs target 0.2 (90% similar) (+0.45)           |
|    |                        |              |              | from the 2020s (next to 2010s) (+0.25)                         |
|    |                        |              |              | diversity penalty: artist Neon Echo already listed 1x (-1.00)  |
|    |                        |              |              | diversity penalty: genre pop already listed 1x (-0.50)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Rooftop Lights         | indie pop    | 5.26         | mood match: happy (+1.00)                                      |
|    | by Indigo Parade       | happy        |              | mood tags uplifting, carefree (2/3) (+0.67)                    |
|    |                        |              |              | energy 0.76 vs target 0.8 (96% similar) (+1.44)                |
|    |                        |              |              | valence 0.81 vs target 0.8 (99% similar) (+0.49)               |
|    |                        |              |              | danceability 0.82 vs target 0.8 (98% similar) (+0.49)          |
|    |                        |              |              | popularity 73 vs target 75 (98% similar) (+0.24)               |
|    |                        |              |              | acousticness 0.35 vs target 0.2 (85% similar) (+0.43)          |
|    |                        |              |              | from the 2010s (+0.50)                                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Gym Hero               | pop          | 4.39         | genre match: pop (+2.00)                                       |
|    | by Max Pulse           | intense      | (base 5.39)  | energy 0.93 vs target 0.8 (87% similar) (+1.30)                |
|    |                        |              |              | valence 0.77 vs target 0.8 (97% similar) (+0.48)               |
|    |                        |              |              | danceability 0.88 vs target 0.8 (92% similar) (+0.46)          |
|    |                        |              |              | popularity 82 vs target 75 (93% similar) (+0.23)               |
|    |                        |              |              | acousticness 0.05 vs target 0.2 (85% similar) (+0.42)          |
|    |                        |              |              | from the 2010s (+0.50)                                         |
|    |                        |              |              | diversity penalty: genre pop already listed 2x (-1.00)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Concrete Poetry        | hip hop      | 3.56         | energy 0.78 vs target 0.8 (98% similar) (+1.47)                |
|    | by Verse Theory        | confident    |              | valence 0.62 vs target 0.8 (82% similar) (+0.41)               |
|    |                        |              |              | danceability 0.86 vs target 0.8 (94% similar) (+0.47)          |
|    |                        |              |              | popularity 75 vs target 75 (100% similar) (+0.25)              |
|    |                        |              |              | acousticness 0.12 vs target 0.2 (92% similar) (+0.46)          |
|    |                        |              |              | from the 2010s (+0.50)                                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: High-Energy Pop ===
Preferences : genre=pop, mood=intense, energy=0.92, danceability=0.85, tempo_bpm=130, mood_tags=['pumped', 'party'], popularity=80, release_decade=2020
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Gym Hero               | pop          | 6.44         | genre match: pop (+2.00)                                       |
|    | by Max Pulse           | intense      |              | mood match: intense (+1.00)                                    |
|    |                        |              |              | mood tags pumped (1/2) (+0.50)                                 |
|    |                        |              |              | energy 0.93 vs target 0.92 (99% similar) (+1.48)               |
|    |                        |              |              | danceability 0.88 vs target 0.85 (97% similar) (+0.48)         |
|    |                        |              |              | tempo_bpm 132 vs target 130 (98% similar) (+0.49)              |
|    |                        |              |              | popularity 82 vs target 80 (98% similar) (+0.24)               |
|    |                        |              |              | from the 2010s (next to 2020s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Bubblegum Skies        | pop          | 5.10         | genre match: pop (+2.00)                                       |
|    | by Neon Echo           | happy        | (base 5.60)  | mood tags party (1/2) (+0.50)                                  |
|    |                        |              |              | energy 0.85 vs target 0.92 (93% similar) (+1.40)               |
|    |                        |              |              | danceability 0.84 vs target 0.85 (99% similar) (+0.49)         |
|    |                        |              |              | tempo_bpm 122 vs target 130 (93% similar) (+0.47)              |
|    |                        |              |              | popularity 85 vs target 80 (95% similar) (+0.24)               |
|    |                        |              |              | from the 2020s (+0.50)                                         |
|    |                        |              |              | diversity penalty: genre pop already listed 1x (-0.50)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Storm Runner           | rock         | 3.51         | mood match: intense (+1.00)                                    |
|    | by Voltline            | intense      |              | energy 0.91 vs target 0.92 (99% similar) (+1.48)               |
|    |                        |              |              | danceability 0.66 vs target 0.85 (81% similar) (+0.41)         |
|    |                        |              |              | tempo_bpm 152 vs target 130 (82% similar) (+0.41)              |
|    |                        |              |              | popularity 66 vs target 80 (86% similar) (+0.21)               |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Pulse Reactor          | edm          | 3.16         | mood tags pumped, party (2/2) (+1.00)                          |
|    | by Max Pulse           | euphoric     | (base 4.16)  | energy 0.95 vs target 0.92 (97% similar) (+1.46)               |
|    |                        |              |              | danceability 0.92 vs target 0.85 (93% similar) (+0.46)         |
|    |                        |              |              | tempo_bpm 128 vs target 130 (98% similar) (+0.49)              |
|    |                        |              |              | popularity 80 vs target 80 (100% similar) (+0.25)              |
|    |                        |              |              | from the 2020s (+0.50)                                         |
|    |                        |              |              | diversity penalty: artist Max Pulse already listed 1x (-1.00)  |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Sunrise City           | pop          | 2.76         | genre match: pop (+2.00)                                       |
|    | by Neon Echo           | happy        | (base 4.76)  | energy 0.82 vs target 0.92 (90% similar) (+1.35)               |
|    |                        |              |              | danceability 0.79 vs target 0.85 (94% similar) (+0.47)         |
|    |                        |              |              | tempo_bpm 118 vs target 130 (90% similar) (+0.45)              |
|    |                        |              |              | popularity 78 vs target 80 (98% similar) (+0.24)               |
|    |                        |              |              | from the 2010s (next to 2020s) (+0.25)                         |
|    |                        |              |              | diversity penalty: artist Neon Echo already listed 1x (-1.00)  |
|    |                        |              |              | diversity penalty: genre pop already listed 2x (-1.00)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: Chill Lofi ===
Preferences : genre=lofi, mood=chill, energy=0.35, acousticness=0.8, instrumentalness=0.9, tempo_bpm=75, mood_tags=['calm', 'study', 'rainy'], release_decade=2020
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Library Rain           | lofi         | 7.45         | genre match: lofi (+2.00)                                      |
|    | by Paper Lanterns      | chill        |              | mood match: chill (+1.00)                                      |
|    |                        |              |              | mood tags calm, study, rainy (3/3) (+1.00)                     |
|    |                        |              |              | energy 0.35 vs target 0.35 (100% similar) (+1.50)              |
|    |                        |              |              | acousticness 0.86 vs target 0.8 (94% similar) (+0.47)          |
|    |                        |              |              | instrumentalness 0.92 vs target 0.9 (98% similar) (+0.49)      |
|    |                        |              |              | tempo_bpm 72 vs target 75 (98% similar) (+0.49)                |
|    |                        |              |              | from the 2020s (+0.50)                                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Rainy Window Beats     | lofi         | 6.94         | genre match: lofi (+2.00)                                      |
|    | by LoRoom              | chill        | (base 7.44)  | mood match: chill (+1.00)                                      |
|    |                        |              |              | mood tags calm, study, rainy (3/3) (+1.00)                     |
|    |                        |              |              | energy 0.38 vs target 0.35 (97% similar) (+1.46)               |
|    |                        |              |              | acousticness 0.8 vs target 0.8 (100% similar) (+0.50)          |
|    |                        |              |              | instrumentalness 0.93 vs target 0.9 (97% similar) (+0.48)      |
|    |                        |              |              | tempo_bpm 74 vs target 75 (99% similar) (+0.50)                |
|    |                        |              |              | from the 2020s (+0.50)                                         |
|    |                        |              |              | diversity penalty: genre lofi already listed 1x (-0.50)        |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Midnight Coding        | lofi         | 5.00         | genre match: lofi (+2.00)                                      |
|    | by LoRoom              | chill        | (base 7.00)  | mood match: chill (+1.00)                                      |
|    |                        |              |              | mood tags calm, study (2/3) (+0.67)                            |
|    |                        |              |              | energy 0.42 vs target 0.35 (93% similar) (+1.40)               |
|    |                        |              |              | acousticness 0.71 vs target 0.8 (91% similar) (+0.45)          |
|    |                        |              |              | instrumentalness 0.88 vs target 0.9 (98% similar) (+0.49)      |
|    |                        |              |              | tempo_bpm 78 vs target 75 (98% similar) (+0.49)                |
|    |                        |              |              | from the 2020s (+0.50)                                         |
|    |                        |              |              | diversity penalty: artist LoRoom already listed 1x (-1.00)     |
|    |                        |              |              | diversity penalty: genre lofi already listed 2x (-1.00)        |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Spacewalk Thoughts     | ambient      | 4.34         | mood match: chill (+1.00)                                      |
|    | by Orbit Bloom         | chill        |              | mood tags calm (1/3) (+0.33)                                   |
|    |                        |              |              | energy 0.28 vs target 0.35 (93% similar) (+1.40)               |
|    |                        |              |              | acousticness 0.92 vs target 0.8 (88% similar) (+0.44)          |
|    |                        |              |              | instrumentalness 0.95 vs target 0.9 (95% similar) (+0.48)      |
|    |                        |              |              | tempo_bpm 60 vs target 75 (88% similar) (+0.44)                |
|    |                        |              |              | from the 2010s (next to 2020s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Paper Boats            | folk         | 3.10         | mood tags rainy (1/3) (+0.33)                                  |
|    | by Willow & Wren       | sad          |              | energy 0.3 vs target 0.35 (95% similar) (+1.42)                |
|    |                        |              |              | acousticness 0.9 vs target 0.8 (90% similar) (+0.45)           |
|    |                        |              |              | instrumentalness 0.2 vs target 0.9 (30% similar) (+0.15)       |
|    |                        |              |              | tempo_bpm 76 vs target 75 (99% similar) (+0.50)                |
|    |                        |              |              | from the 2010s (next to 2020s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: Deep Intense Rock ===
Preferences : genre=rock, mood=intense, energy=0.9, valence=0.4, tempo_bpm=150, liveness=0.3, mood_tags=['aggressive', 'adrenaline'], release_decade=2000
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Storm Runner           | rock         | 7.18         | genre match: rock (+2.00)                                      |
|    | by Voltline            | intense      |              | mood match: intense (+1.00)                                    |
|    |                        |              |              | mood tags aggressive, adrenaline (2/2) (+1.00)                 |
|    |                        |              |              | energy 0.91 vs target 0.9 (99% similar) (+1.48)                |
|    |                        |              |              | valence 0.48 vs target 0.4 (92% similar) (+0.46)               |
|    |                        |              |              | liveness 0.3 vs target 0.3 (100% similar) (+0.25)              |
|    |                        |              |              | tempo_bpm 152 vs target 150 (98% similar) (+0.49)              |
|    |                        |              |              | from the 2000s (+0.50)                                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Gym Hero               | pop          | 4.18         | mood match: intense (+1.00)                                    |
|    | by Max Pulse           | intense      |              | mood tags adrenaline (1/2) (+0.50)                             |
|    |                        |              |              | energy 0.93 vs target 0.9 (97% similar) (+1.46)                |
|    |                        |              |              | valence 0.77 vs target 0.4 (63% similar) (+0.32)               |
|    |                        |              |              | liveness 0.2 vs target 0.3 (90% similar) (+0.23)               |
|    |                        |              |              | tempo_bpm 132 vs target 150 (85% similar) (+0.42)              |
|    |                        |              |              | from the 2010s (next to 2000s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Iron Cathedral         | metal        | 3.71         | mood tags aggressive, adrenaline (2/2) (+1.00)                 |
|    | by Grave Signal        | angry        |              | energy 0.97 vs target 0.9 (93% similar) (+1.40)                |
|    |                        |              |              | valence 0.25 vs target 0.4 (85% similar) (+0.42)               |
|    |                        |              |              | liveness 0.4 vs target 0.3 (90% similar) (+0.22)               |
|    |                        |              |              | tempo_bpm 168 vs target 150 (85% similar) (+0.42)              |
|    |                        |              |              | from the 1990s (next to 2000s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Rooftop Lights         | indie pop    | 2.46         | energy 0.76 vs target 0.9 (86% similar) (+1.29)                |
|    | by Indigo Parade       | happy        |              | valence 0.81 vs target 0.4 (59% similar) (+0.29)               |
|    |                        |              |              | liveness 0.25 vs target 0.3 (95% similar) (+0.24)              |
|    |                        |              |              | tempo_bpm 124 vs target 150 (78% similar) (+0.39)              |
|    |                        |              |              | from the 2010s (next to 2000s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Concrete Poetry        | hip hop      | 2.45         | energy 0.78 vs target 0.9 (88% similar) (+1.32)                |
|    | by Verse Theory        | confident    |              | valence 0.62 vs target 0.4 (78% similar) (+0.39)               |
|    |                        |              |              | liveness 0.18 vs target 0.3 (88% similar) (+0.22)              |
|    |                        |              |              | tempo_bpm 95 vs target 150 (54% similar) (+0.27)               |
|    |                        |              |              | from the 2010s (next to 2000s) (+0.25)                         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: Edge: High Energy + Sad Mood (conflicting) ===
Preferences : genre=folk, mood=sad, energy=0.95, valence=0.1, tempo_bpm=160
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Paper Boats            | folk         | 4.09         | genre match: folk (+2.00)                                      |
|    | by Willow & Wren       | sad          |              | mood match: sad (+1.00)                                        |
|    |                        |              |              | energy 0.3 vs target 0.95 (35% similar) (+0.53)                |
|    |                        |              |              | valence 0.28 vs target 0.1 (82% similar) (+0.41)               |
|    |                        |              |              | tempo_bpm 76 vs target 160 (30% similar) (+0.15)               |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Iron Cathedral         | metal        | 2.36         | energy 0.97 vs target 0.95 (98% similar) (+1.47)               |
|    | by Grave Signal        | angry        |              | valence 0.25 vs target 0.1 (85% similar) (+0.42)               |
|    |                        |              |              | tempo_bpm 168 vs target 160 (93% similar) (+0.47)              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Storm Runner           | rock         | 2.22         | energy 0.91 vs target 0.95 (96% similar) (+1.44)               |
|    | by Voltline            | intense      |              | valence 0.48 vs target 0.1 (62% similar) (+0.31)               |
|    |                        |              |              | tempo_bpm 152 vs target 160 (93% similar) (+0.47)              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Pulse Reactor          | edm          | 2.02         | energy 0.95 vs target 0.95 (100% similar) (+1.50)              |
|    | by Max Pulse           | euphoric     |              | valence 0.8 vs target 0.1 (30% similar) (+0.15)                |
|    |                        |              |              | tempo_bpm 128 vs target 160 (73% similar) (+0.37)              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Bubblegum Skies        | pop          | 1.79         | energy 0.85 vs target 0.95 (90% similar) (+1.35)               |
|    | by Neon Echo           | happy        |              | valence 0.9 vs target 0.1 (20% similar) (+0.10)                |
|    |                        |              |              | tempo_bpm 122 vs target 160 (68% similar) (+0.34)              |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: Edge: Boundary Targets (all 0.0 / 1.0, no genre or mood) ===
Preferences : energy=0.0, valence=0.0, acousticness=1.0, instrumentalness=1.0, danceability=0.0
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Moonlit Sonata Redux   | classical    | 2.89         | energy 0.22 vs target 0 (78% similar) (+1.17)                  |
|    | by Clara Vey           | melancholic  |              | valence 0.3 vs target 0 (70% similar) (+0.35)                  |
|    |                        |              |              | danceability 0.2 vs target 0 (80% similar) (+0.40)             |
|    |                        |              |              | acousticness 0.97 vs target 1 (97% similar) (+0.48)            |
|    |                        |              |              | instrumentalness 0.98 vs target 1 (98% similar) (+0.49)        |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Spacewalk Thoughts     | ambient      | 2.48         | energy 0.28 vs target 0 (72% similar) (+1.08)                  |
|    | by Orbit Bloom         | chill        |              | valence 0.65 vs target 0 (35% similar) (+0.17)                 |
|    |                        |              |              | danceability 0.41 vs target 0 (59% similar) (+0.30)            |
|    |                        |              |              | acousticness 0.92 vs target 1 (92% similar) (+0.46)            |
|    |                        |              |              | instrumentalness 0.95 vs target 1 (95% similar) (+0.47)        |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Library Rain           | lofi         | 2.28         | energy 0.35 vs target 0 (65% similar) (+0.98)                  |
|    | by Paper Lanterns      | chill        |              | valence 0.6 vs target 0 (40% similar) (+0.20)                  |
|    |                        |              |              | danceability 0.58 vs target 0 (42% similar) (+0.21)            |
|    |                        |              |              | acousticness 0.86 vs target 1 (86% similar) (+0.43)            |
|    |                        |              |              | instrumentalness 0.92 vs target 1 (92% similar) (+0.46)        |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Paper Boats            | folk         | 2.26         | energy 0.3 vs target 0 (70% similar) (+1.05)                   |
|    | by Willow & Wren       | sad          |              | valence 0.28 vs target 0 (72% similar) (+0.36)                 |
|    |                        |              |              | danceability 0.4 vs target 0 (60% similar) (+0.30)             |
|    |                        |              |              | acousticness 0.9 vs target 1 (90% similar) (+0.45)             |
|    |                        |              |              | instrumentalness 0.2 vs target 1 (20% similar) (+0.10)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Coffee Shop Stories    | jazz         | 2.13         | energy 0.37 vs target 0 (63% similar) (+0.95)                  |
|    | by Slow Stereo         | relaxed      |              | valence 0.71 vs target 0 (29% similar) (+0.15)                 |
|    |                        |              |              | danceability 0.54 vs target 0 (46% similar) (+0.23)            |
|    |                        |              |              | acousticness 0.89 vs target 1 (89% similar) (+0.45)            |
|    |                        |              |              | instrumentalness 0.7 vs target 1 (70% similar) (+0.35)         |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+

=== Profile: Edge: Unknown Genre + Messy Input ('k-pop', ' HAPPY ') ===
Preferences : genre=k-pop, mood= HAPPY , energy=0.6
Scoring mode: balanced | Diversity penalty: ON | Top 5
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| #  | Song                   | Genre / Mood | Score        | Why (points earned)                                            |
+====+========================+==============+==============+================================================================+
| 1  | Rooftop Lights         | indie pop    | 2.26         | mood match: happy (+1.00)                                      |
|    | by Indigo Parade       | happy        |              | energy 0.76 vs target 0.6 (84% similar) (+1.26)                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 2  | Sunrise City           | pop          | 2.17         | mood match: happy (+1.00)                                      |
|    | by Neon Echo           | happy        |              | energy 0.82 vs target 0.6 (78% similar) (+1.17)                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 3  | Island Time            | reggae       | 1.47         | energy 0.58 vs target 0.6 (98% similar) (+1.47)                |
|    | by Sunset Collective   | relaxed      |              |                                                                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 4  | Dusty Backroads        | country      | 1.43         | energy 0.55 vs target 0.6 (95% similar) (+1.43)                |
|    | by Copper Creek        | nostalgic    |              |                                                                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
| 5  | Slow Honey             | r&b          | 1.35         | energy 0.5 vs target 0.6 (90% similar) (+1.35)                 |
|    | by Amber Lane          | romantic     |              |                                                                |
+----+------------------------+--------------+--------------+----------------------------------------------------------------+
```

</details>

### Why the #1 songs win (using the actual weights)

- **Sunrise City (Happy Pop, 7.67):** it is the only song that gets genre (+2.0), mood (+1.0), all 3 mood tags (+1.0) **and** the exact decade (+0.5). *Bubblegum Skies* matches genre and mood too, but only 2/3 tags (+0.67) and a neighbouring decade (+0.25). That puts its base at 6.96.
- **Gym Hero (High-Energy Pop, 6.44):** it is the only song that is both pop **and** intense, and its energy 0.93 is almost exactly the 0.92 target.
- **Library Rain vs. Rainy Window Beats (Chill Lofi, 7.45 vs 7.44):** both get genre, mood, all three tags and the decade. Library Rain wins by 0.01 because its energy is exactly 0.35 (+1.50 vs +1.46). *Focus Flow* is lofi but its mood is "focused," not "chill," so it misses the +1.0 mood point and sits at 6.06.
- **Storm Runner (Rock, 7.18):** it is the only rock song in the catalog. That is also why #2–#5 drop to ≤ 4.18.
- **Paper Boats (Sad but Hyper, 4.09):** genre + mood give +3.0 even though its energy is only 35% similar (+0.53). *Iron Cathedral* matches the energy (+1.47), valence and tempo, but it has no label match, so it reaches only 2.36.
- **Moonlit Sonata Redux (Boundary, 2.89):** it has the lowest energy (0.22) and the highest acousticness (0.97) and instrumentalness (0.98) in the catalog, so it is closest to the 0.0/1.0 targets.
- **Rooftop Lights (Ghost Genre, 2.26):** "k-pop" matches nothing. `" HAPPY "` is cleaned up and matches the three happy songs (+1.0). Among those, Rooftop Lights' energy 0.76 is closest to 0.6.

### Songs that repeat, rankings that change

- **No song dominates.** Across the 7 top-5 lists, no song appears more than 3 times. *Gym Hero, Sunrise City, Bubblegum Skies, Storm Runner, Rooftop Lights* and *Paper Boats* each appear exactly 3 times. The energy closeness weight (1.5) is smaller than the genre + mood weight (3.0), so no single "average" song wins everywhere.
- **Gym Hero moves around a lot.** It is #1 for High-Energy Pop, #2 for Rock (shared "intense" mood), #4 for Happy Pop, and it is pushed out of Sad but Hyper by the artist penalty (Max Pulse was already picked with *Pulse Reactor*).
- **Similar profiles:** Happy Pop and High-Energy Pop share 3 of 5 songs. Chill Lofi and Boundary Silence share 3 of 5.

### Surprises

1. **The rock fan gets pop and hip hop.** After *Storm Runner* and *Iron Cathedral*, the Rock profile is filled with *Rooftop Lights* (indie pop) and *Concrete Poetry* (hip hop). Their energy (0.76/0.78) is the next closest to 0.9. That is a catalog limitation, not a sensible taste match.
2. **"Indie pop" is not "pop."** Rooftop Lights never gets the pop genre point. In the Rock profile, the genre diversity penalty also treats it as a different genre from Gym Hero (pop).
3. **The penalty did not move the strong #2.** For Happy Pop, *Bubblegum Skies* lost 1.5 points (same artist and genre as Sunrise City) but still stayed #2 at 5.46, ahead of Rooftop Lights at 5.26. The penalty reshuffles close calls; it does not override a clearly better match.
4. **Paper Boats appears for three opposite reasons:** genre + mood in Sad but Hyper, a "rainy" tag plus low energy in Chill Lofi, and low energy/valence in Boundary.

### Comparing every pair of profiles

| Pair | Shared top-5 songs | What changes and why |
|---|---|---|
| Happy Pop vs High-Energy Pop | Bubblegum Skies, Gym Hero, Sunrise City | Same genre, but #1 flips: mood (happy vs intense) and energy target (0.8 vs 0.92) decide between the pop songs. |
| Happy Pop vs Chill Lofi | none | Energy targets 0.8 vs 0.35 pull from opposite ends; the average energy of the top 5 is 0.83 vs 0.35. |
| Happy Pop vs Deep Intense Rock | Concrete Poetry, Gym Hero, Rooftop Lights | With only one rock song, the rock list falls back on the same upbeat high-energy songs the pop fan gets. |
| Happy Pop vs Sad but Hyper | Bubblegum Skies | Valence target 0.1 vs 0.8: happy songs get only 20% valence similarity for the sad user, so only one squeaks in at #5. |
| Happy Pop vs Boundary Silence | none | Boundary wants energy 0 and acousticness 1, while Happy Pop wants energy 0.8 and acousticness 0.2. No overlap. |
| Happy Pop vs Ghost Genre | Rooftop Lights, Sunrise City | Both get the "happy" mood point, but Ghost Genre gets no genre point, so its scores are ~2 instead of ~7. |
| High-Energy Pop vs Chill Lofi | none | Tempo 130 vs 75 and energy 0.92 vs 0.35. Complete opposites. |
| High-Energy Pop vs Deep Intense Rock | Gym Hero, Storm Runner | Both like "intense"; the genre point (+2.0) decides which of the two is #1. |
| High-Energy Pop vs Sad but Hyper | Bubblegum Skies, Pulse Reactor, Storm Runner | Both want energy above 0.9, but the sad user's folk + sad labels put low-energy Paper Boats first. |
| High-Energy Pop vs Boundary Silence | none | Danceability 0.85 vs 0.0 and energy 0.92 vs 0.0. |
| High-Energy Pop vs Ghost Genre | Sunrise City | Ghost Genre's mid energy (0.6) brings in mid-energy songs (Island Time 0.58, Dusty Backroads 0.55) that High-Energy Pop never ranks. |
| Chill Lofi vs Deep Intense Rock | none | Opposite energy, tempo and mood tags. |
| Chill Lofi vs Sad but Hyper | Paper Boats | The same song for different reasons: "rainy" tag + low energy vs folk + sad labels. |
| Chill Lofi vs Boundary Silence | Library Rain, Paper Boats, Spacewalk Thoughts | Both reward low energy, high acousticness and instrumentalness. Boundary has no genre, so classical (Moonlit Sonata Redux) beats the lofi songs. |
| Chill Lofi vs Ghost Genre | none | Ghost Genre's "happy" mood and 0.6 energy match none of the chill songs. |
| Deep Intense Rock vs Sad but Hyper | Iron Cathedral, Storm Runner | Rock ranks Storm Runner #1 via genre; the sad user ranks Iron Cathedral higher because of its lower valence (0.25 vs a 0.1 target). |
| Deep Intense Rock vs Boundary Silence | none | Energy 0.9 vs 0.0. |
| Deep Intense Rock vs Ghost Genre | Rooftop Lights | Rooftop Lights is "filler" for rock (energy) and the best "happy" match for Ghost Genre. |
| Sad but Hyper vs Boundary Silence | Paper Boats | Both want low valence; Paper Boats (valence 0.28, acoustic 0.90) fits both. |
| Sad but Hyper vs Ghost Genre | none | Opposite valence goals, and their energy targets differ (0.95 vs 0.6). |
| Boundary Silence vs Ghost Genre | none | Boundary wants the calmest, least danceable songs; Ghost Genre's "happy" mood point and 0.6 energy target favor upbeat, mid-energy songs instead. |

**Do the outputs make sense?** For the three normal listeners, yes. The #1 picks match the profile, and the reasons explain why. For the edge cases, the outputs follow the rules but expose limits. The conflicting user gets a quiet sad song because labels outweigh energy. The k-pop fan gets low-confidence picks (all scores ≤ 2.26). The rock fan's list fills with non-rock songs.

### Experiment: weight shift

- **Original logic (balanced):** genre 2.0, energy 1.5.
- **Change:** energy ×2 → **3.0**, genre ×0.5 → **1.0**. Everything else stays the same. Diversity was OFF to isolate the effect of the weights.
- **How to run:** `python -m src.main --experiment`. The experiment is a separate `ScoringMode` object in `src/main.py`. The default configuration was never changed, so nothing needed to be restored.

```text
$ python -m src.main --experiment
Loaded 20 songs from data/songs.csv

Experiment: Balanced weights, but energy 1.5 -> 3.0 and genre 2.0 -> 1.0.

--- Default: Happy Pop (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Sunrise City (7.67)            | Sunrise City (8.14)            |
+----+--------------------------------+--------------------------------+
| 2  | Bubblegum Skies (6.96)         | Bubblegum Skies (7.38)         |
+----+--------------------------------+--------------------------------+
| 3  | Gym Hero (5.39)                | Rooftop Lights (6.70)          |
+----+--------------------------------+--------------------------------+
| 4  | Rooftop Lights (5.26)          | Gym Hero (5.70)                |
+----+--------------------------------+--------------------------------+
| 5  | Concrete Poetry (3.56)         | Concrete Poetry (5.03)         |
+----+--------------------------------+--------------------------------+

--- High-Energy Pop (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Gym Hero (6.44)                | Gym Hero (6.93)                |
+----+--------------------------------+--------------------------------+
| 2  | Bubblegum Skies (5.60)         | Bubblegum Skies (5.99)         |
+----+--------------------------------+--------------------------------+
| 3  | Sunrise City (4.76)            | Pulse Reactor (5.61)           |
+----+--------------------------------+--------------------------------+
| 4  | Pulse Reactor (4.16)           | Sunrise City (5.11)            |
+----+--------------------------------+--------------------------------+
| 5  | Storm Runner (3.51)            | Storm Runner (5.00)            |
+----+--------------------------------+--------------------------------+

--- Chill Lofi (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Library Rain (7.45)            | Library Rain (7.95)            |
+----+--------------------------------+--------------------------------+
| 2  | Rainy Window Beats (7.44)      | Rainy Window Beats (7.89)      |
+----+--------------------------------+--------------------------------+
| 3  | Midnight Coding (7.00)         | Midnight Coding (7.39)         |
+----+--------------------------------+--------------------------------+
| 4  | Focus Flow (6.06)              | Focus Flow (6.49)              |
+----+--------------------------------+--------------------------------+
| 5  | Spacewalk Thoughts (4.34)      | Spacewalk Thoughts (5.73)      |
+----+--------------------------------+--------------------------------+

--- Deep Intense Rock (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Storm Runner (7.18)            | Storm Runner (7.67)            |
+----+--------------------------------+--------------------------------+
| 2  | Gym Hero (4.18)                | Gym Hero (5.63)                |
+----+--------------------------------+--------------------------------+
| 3  | Iron Cathedral (3.71)          | Iron Cathedral (5.10)          |
+----+--------------------------------+--------------------------------+
| 4  | Sunrise City (2.49)            | Sunrise City (3.87)            |
+----+--------------------------------+--------------------------------+
| 5  | Rooftop Lights (2.46)          | Pulse Reactor (3.80)           |
+----+--------------------------------+--------------------------------+

--- Edge: High Energy + Sad Mood (conflicting) (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Paper Boats (4.09)             | Iron Cathedral (3.83)          |
+----+--------------------------------+--------------------------------+
| 2  | Iron Cathedral (2.36)          | Storm Runner (3.66)            |
+----+--------------------------------+--------------------------------+
| 3  | Storm Runner (2.22)            | Paper Boats (3.61)             |
+----+--------------------------------+--------------------------------+
| 4  | Pulse Reactor (2.02)           | Pulse Reactor (3.52)           |
+----+--------------------------------+--------------------------------+
| 5  | Gym Hero (2.01)                | Gym Hero (3.48)                |
+----+--------------------------------+--------------------------------+

--- Edge: Boundary Targets (all 0.0 / 1.0, no genre or mood) (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Moonlit Sonata Redux (2.89)    | Moonlit Sonata Redux (4.06)    |
+----+--------------------------------+--------------------------------+
| 2  | Spacewalk Thoughts (2.48)      | Spacewalk Thoughts (3.56)      |
+----+--------------------------------+--------------------------------+
| 3  | Library Rain (2.28)            | Paper Boats (3.31)             |
+----+--------------------------------+--------------------------------+
| 4  | Paper Boats (2.26)             | Library Rain (3.25)            |
+----+--------------------------------+--------------------------------+
| 5  | Rainy Window Beats (2.24)      | Rainy Window Beats (3.17)      |
+----+--------------------------------+--------------------------------+

--- Edge: Unknown Genre + Messy Input ('k-pop', ' HAPPY ') (diversity OFF to isolate weights) ---
+----+--------------------------------+--------------------------------+
| #  | baseline (balanced)            | energy x2, genre x0.5          |
+====+================================+================================+
| 1  | Rooftop Lights (2.26)          | Rooftop Lights (3.52)          |
+----+--------------------------------+--------------------------------+
| 2  | Sunrise City (2.17)            | Sunrise City (3.34)            |
+----+--------------------------------+--------------------------------+
| 3  | Bubblegum Skies (2.12)         | Bubblegum Skies (3.25)         |
+----+--------------------------------+--------------------------------+
| 4  | Island Time (1.47)             | Island Time (2.94)             |
+----+--------------------------------+--------------------------------+
| 5  | Dusty Backroads (1.43)         | Dusty Backroads (2.85)         |
+----+--------------------------------+--------------------------------+
```

**Observed changes (from the output above):**

- **Membership barely changed.** The set of top-5 songs changed for only **1 of 7** profiles: Deep Intense Rock swapped Rooftop Lights (energy 0.76) for Pulse Reactor (energy 0.95). Everywhere else the same five songs were reordered.
- **Biggest reorder: Sad but Hyper.** Paper Boats fell from #1 to #3, and Iron Cathedral (energy 0.97) became #1. Energy now outweighs the folk label.
- **Songs without a genre match moved up.** Rooftop Lights passed Gym Hero for Happy Pop. Pulse Reactor (edm) passed Sunrise City for High-Energy Pop.
- **No change in order** for Chill Lofi and Ghost Genre. The lofi songs are also the closest in energy, and Ghost Genre's only genre was unmatched anyway.
- **Conclusion:** the results became **different and more energy-driven, not clearly more accurate.** Without real user feedback, I cannot say which version is "right." For the conflicting profile, the answer depends on whether the user cared more about "sad folk" or "high energy." The final system keeps the balanced weights and offers `energy-focused` mode for users who want energy to dominate.

### Diversity check

`python -m src.main --diversity-demo --profile chill-lofi` (output in the [README](README.md#diversity-penalty-in-action)):

- **OFF:** 4 lofi songs, 3 by LoRoom (Library Rain, Rainy Window Beats, Midnight Coding, Focus Flow, Spacewalk Thoughts).
- **ON:** 3 lofi songs, 2 by LoRoom, plus ambient (Spacewalk Thoughts) and folk (Paper Boats). *Focus Flow* (base 6.06) would have been the third LoRoom song and fourth lofi song, so its penalty (−2.0 artist, −1.5 genre) dropped it below the others.
- **Happy Pop:** Gym Hero and Rooftop Lights swapped places (#3/#4). Bubblegum Skies stayed #2 despite its −1.5 penalty.
- **Lists are more varied but still relevant:** the strongest matches stay on top, and no genre or artist disappeared entirely.

### Automated tests

`python -m pytest` runs **25 tests, all passing.** They cover loading and types, invalid/missing rows, genre/mood/closeness scoring, score = sum of reasons, ordering and top-k, the scoring modes, the diversity penalty, and 6 CLI commands.

---

## 7. Intended Use and Non-Intended Use

**Intended use**

- Classroom exploration of how content-based recommenders score and rank items.
- Experimenting with weights, modes and diversity, and seeing the effect immediately in an explainable table.

**Not intended for**

- Real users or real products. The catalog is 20 invented songs.
- Judging real artists' popularity or quality. All popularity values are simulated.
- Inferring anything about a person (mood, mental state, identity) from their music preferences.
- Any decision with consequences, such as royalties, playlist placement or advertising.

---

## 8. Ideas for Improvement

1. **Related genres instead of exact matches:** give partial credit for related labels (pop ↔ indie pop, rock ↔ metal) using a small similarity table, so fans of niche genres get better fallbacks.
2. **A bigger, more balanced catalog:** at least several songs per genre and more mid-energy songs. Real (licensed, public) audio features would replace the invented values.
3. **Learn from feedback:** let the user like or skip songs and adjust the weights or targets, which is a first step toward the behavioral signals real platforms use. A "confidence" note when the best score is low (like the k-pop case) would make weak matches obvious.

---

## 9. Personal Reflection

> **DRAFT for the student to review and personalize.** The AI assistant wrote this from the work actually done in this repository. It does not know your personal experience. Replace the bracketed prompts with your own thoughts.

- **Biggest learning moment:** *(draft)* A recommender's "intelligence" here is a short list of hand-picked weights. Doubling one weight (energy) reordered several top-5 lists without any new data. *[Add the moment that stood out to you.]*
- **How AI tools helped:** *(draft)* An AI coding agent (Claude Code) inspected the starter files and implemented `load_songs`, `score_song` and `recommend_songs`, the four scoring modes, the diversity penalty, the table output and 23 new tests. It ran the program and pasted the real output into these docs. *[Describe how you used it and what you would do differently.]*
- **When AI work needed checking:** *(draft)* One AI-written test assumed `energy-focused` mode would put a non-pop song first for the High-Energy Pop profile. The real run showed *Gym Hero* wins in every mode, so the test was wrong, not the code. It was rewritten to check behavior the program actually showed. The AI also had to verify that the reasons add up to the displayed score. *[Add anything you checked or corrected yourself.]*
- **What was surprising:** *(draft)* Simple rules already produce believable results for clear tastes. They also produce odd ones (a rock fan getting hip hop) as soon as the catalog runs out of matching songs. *[Your reaction?]*
- **What I would build next:** *(draft)* Related-genre partial credit and like/skip feedback. *[Your idea?]*
