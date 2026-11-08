"""Tests for loading, scoring, ranking, modes, diversity and the CLI."""

import subprocess
import sys
from pathlib import Path

import pytest

from src.recommender import (SCORING_MODES, get_mode, load_songs, rank_songs,
                             recommend_songs, score_song)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "songs.csv"


def make_song(**overrides):
    """A minimal song dict with sensible defaults."""
    song = {"id": 1, "title": "Song", "artist": "A", "genre": "pop", "mood": "happy",
            "energy": 0.5, "tempo_bpm": 100.0, "valence": 0.5, "danceability": 0.5,
            "acousticness": 0.5, "popularity": 50, "release_decade": 2010,
            "instrumentalness": 0.5, "liveness": 0.2, "mood_tags": []}
    song.update(overrides)
    return song


# --- load_songs -------------------------------------------------------------

def test_load_real_dataset_types():
    songs = load_songs(str(DATA))
    assert len(songs) >= 15  # 10 starter songs + at least 5 new ones
    first = songs[0]
    assert first["title"] == "Sunrise City"  # original starter songs preserved
    assert isinstance(first["id"], int)
    assert isinstance(first["energy"], float)
    assert isinstance(first["tempo_bpm"], float)
    assert isinstance(first["popularity"], int)
    assert isinstance(first["release_decade"], int)
    assert isinstance(first["instrumentalness"], float)
    assert isinstance(first["liveness"], float)
    assert first["mood_tags"] == ["uplifting", "sunny", "carefree"]
    for song in songs:
        assert 0.0 <= song["energy"] <= 1.0
        assert 0 <= song["popularity"] <= 100
        assert song["mood_tags"], f"{song['title']} has no mood tags"


def test_load_handles_missing_and_invalid_values(tmp_path, capsys):
    csv_file = tmp_path / "songs.csv"
    csv_file.write_text(
        "id,title,artist,genre,mood,energy,tempo_bpm,popularity,mood_tags\n"
        "1,Good,X,pop,happy,0.5,100,50,calm\n"
        "2,No Energy,X,pop,happy,,100,50,calm\n"        # required value missing -> skipped
        "3,Bad Pop,,rock,sad,0.7,90,abc,\n"            # optional invalid -> None, kept
        "4,Too Loud,X,rock,sad,1.7,90,50,\n"           # energy out of range -> skipped
        "1,Duplicate,X,pop,happy,0.5,100,50,calm\n",   # duplicate id -> skipped
        encoding="utf-8",
    )
    songs = load_songs(str(csv_file))
    assert [s["title"] for s in songs] == ["Good", "Bad Pop"]
    assert songs[1]["popularity"] is None
    assert songs[1]["artist"] == ""
    assert songs[1]["mood_tags"] == []
    output = capsys.readouterr().out
    assert output.count("skipped") == 3  # every dropped row is reported, never silent


# --- score_song -------------------------------------------------------------

def test_genre_and_mood_points_and_reasons():
    score, reasons = score_song({"genre": "pop", "mood": "happy"}, make_song())
    assert score == pytest.approx(3.0)
    assert "genre match: pop (+2.00)" in reasons
    assert "mood match: happy (+1.00)" in reasons


def test_matching_ignores_case_and_spaces():
    score, _ = score_song({"genre": " POP ", "mood": "Happy"}, make_song())
    assert score == pytest.approx(3.0)


def test_numeric_similarity_rewards_closeness_not_size():
    song = make_song(energy=0.70)
    near, _ = score_song({"energy": 0.70}, song)
    far, _ = score_song({"energy": 0.10}, song)
    assert near > far
    # A lower-energy song should win for a low-energy target.
    calm, _ = score_song({"energy": 0.2}, make_song(energy=0.25))
    loud, _ = score_song({"energy": 0.2}, make_song(energy=0.95))
    assert calm > loud


def test_score_equals_sum_of_reason_points():
    songs = load_songs(str(DATA))
    prefs = {"genre": "lofi", "mood": "chill", "energy": 0.35, "mood_tags": ["calm", "study"],
             "release_decade": 2020, "popularity": 60, "tempo_bpm": 75}
    for song in songs:
        score, reasons = score_song(prefs, song)
        points = sum(float(r.rsplit("(+", 1)[1].rstrip(")")) for r in reasons)
        assert score == pytest.approx(points, abs=0.001)


def test_advanced_features_change_the_score():
    base = make_song(mood_tags=["calm", "study"], release_decade=2020, popularity=90)
    prefs = {"mood_tags": ["calm", "rainy"], "release_decade": 2020, "popularity": 90,
             "instrumentalness": 0.5, "liveness": 0.2}
    score, reasons = score_song(prefs, base)
    text = " ".join(reasons)
    assert "mood tags calm (1/2)" in text
    assert "from the 2020s" in text
    assert "popularity" in text and "instrumentalness" in text and "liveness" in text
    neighbour_score, _ = score_song({"release_decade": 2010}, base)
    far_score, _ = score_song({"release_decade": 1970}, base)
    assert neighbour_score == pytest.approx(0.25) and far_score == 0


def test_missing_song_values_are_skipped_not_crashing():
    score, reasons = score_song({"energy": 0.5, "popularity": 50}, make_song(popularity=None))
    assert score == pytest.approx(1.5)
    assert all("popularity" not in r for r in reasons)


def test_empty_preferences_score_zero():
    assert score_song({}, make_song()) == (0.0, [])


# --- ranking ----------------------------------------------------------------

def test_recommendations_sorted_and_top_k():
    songs = load_songs(str(DATA))
    results = recommend_songs({"genre": "pop", "mood": "happy", "energy": 0.8}, songs, k=5)
    assert len(results) == 5
    scores = [score for _, score, _ in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0][1] > 0 and isinstance(results[0][2], str)
    assert len({song["id"] for song, _, _ in results}) == 5


def test_k_edge_cases_and_no_duplicates():
    songs = load_songs(str(DATA))
    assert recommend_songs({"energy": 0.5}, songs, k=0) == []
    everything = recommend_songs({"energy": 0.5}, songs + songs, k=100)
    assert len(everything) == len(songs)  # duplicates removed, k larger than catalog is fine


def test_original_list_is_not_reordered():
    songs = load_songs(str(DATA))
    before = [s["id"] for s in songs]
    rank_songs({"energy": 0.1}, songs, k=5)
    assert [s["id"] for s in songs] == before


# --- scoring modes ----------------------------------------------------------

def test_modes_have_different_weights_and_unknown_mode_fails():
    weight_sets = {tuple(sorted(m.weights.items())) for m in SCORING_MODES.values()}
    assert len(weight_sets) == len(SCORING_MODES) >= 2
    with pytest.raises(ValueError):
        get_mode("does-not-exist")


def test_modes_change_rankings():
    songs = load_songs(str(DATA))
    prefs = {"genre": "pop", "mood": "intense", "energy": 0.92, "danceability": 0.85,
             "tempo_bpm": 130, "mood_tags": ["pumped", "party"]}
    tops = {name: [r["song"]["title"] for r in rank_songs(prefs, songs, k=5, mode=name)]
            for name in SCORING_MODES}
    assert len({tuple(t) for t in tops.values()}) > 1
    # genre-first keeps all pop songs ahead
    assert all(s["genre"] == "pop" for s in
               [r["song"] for r in rank_songs(prefs, songs, k=3, mode="genre-first")])
    # Conflicting profile: genre/mood modes pick the sad folk song,
    # energy-focused picks a high-energy song instead.
    conflict = {"genre": "folk", "mood": "sad", "energy": 0.95, "valence": 0.1, "tempo_bpm": 160}
    assert rank_songs(conflict, songs, k=1, mode="genre-first")[0]["song"]["genre"] == "folk"
    assert rank_songs(conflict, songs, k=1, mode="energy-focused")[0]["song"]["energy"] >= 0.9


# --- diversity --------------------------------------------------------------

def test_diversity_penalty_uses_already_selected_songs():
    songs = [
        make_song(id=1, title="A1", artist="Same", genre="lofi", energy=0.40),
        make_song(id=2, title="A2", artist="Same", genre="lofi", energy=0.41),
        make_song(id=3, title="B1", artist="Other", genre="jazz", energy=0.30),
    ]
    prefs = {"energy": 0.4}
    plain = rank_songs(prefs, songs, k=3, diversity=False)
    diverse = rank_songs(prefs, songs, k=3, diversity=True)
    assert [r["song"]["title"] for r in plain] == ["A1", "A2", "B1"]
    assert [r["song"]["title"] for r in diverse] == ["A1", "B1", "A2"]
    # first pick is never penalised; base score is preserved next to the final score
    assert diverse[0]["penalty"] == 0
    a2 = diverse[2]
    assert a2["penalty"] == pytest.approx(1.5)  # artist 1.0 + genre 0.5
    assert a2["final_score"] == pytest.approx(a2["base_score"] - 1.5)
    assert any("diversity penalty" in reason for reason in a2["reasons"])
    # penalised songs are still recommended, not removed
    assert len(diverse) == 3


def test_missing_artist_is_not_treated_as_repeat():
    songs = [make_song(id=1, title="X", artist="", genre="a"),
             make_song(id=2, title="Y", artist="", genre="b")]
    results = rank_songs({"energy": 0.5}, songs, k=2, diversity=True)
    assert all(r["penalty"] == 0 for r in results)


def test_diversity_reduces_repeated_artists_on_real_data():
    songs = load_songs(str(DATA))
    prefs = {"genre": "lofi", "mood": "chill", "energy": 0.35, "instrumentalness": 0.9}
    plain = rank_songs(prefs, songs, k=5, diversity=False)
    diverse = rank_songs(prefs, songs, k=5, diversity=True)
    def max_repeats(results, key):
        values = [r["song"][key] for r in results]
        return max(values.count(v) for v in values)
    assert max_repeats(diverse, "artist") < max_repeats(plain, "artist")
    finals = [r["final_score"] for r in diverse]
    assert finals == sorted(finals, reverse=True)


# --- CLI --------------------------------------------------------------------

@pytest.mark.parametrize("extra", [[], ["--profile", "all"], ["--mode", "mood-first"],
                                   ["--compare-modes"], ["--experiment"], ["--diversity-demo"]])
def test_cli_runs(extra):
    result = subprocess.run([sys.executable, "-m", "src.main", *extra], cwd=ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "Loaded 20 songs" in result.stdout
