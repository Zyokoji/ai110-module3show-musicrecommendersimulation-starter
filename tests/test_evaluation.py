"""Tests for the evaluation harness."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from evaluation.run_eval import check_expectations, run_evaluation, write_chart
from src.guardrails import GuardrailError
from src.workflow import build_workflow

ROOT = Path(__file__).resolve().parent.parent


class FakeResult:
    """Minimal stand-in for WorkflowResult."""
    def __init__(self, songs, warnings=(), label="high"):
        self.recommendations = [{"song": s} for s in songs]
        self.warnings = list(warnings)
        self.confidence_label = label


def song(genre="pop", energy=0.5, valence=0.5, mood="happy", tags=()):
    return {"title": f"{genre}-{energy}", "genre": genre, "energy": energy, "valence": valence,
            "mood": mood, "mood_tags": list(tags), "danceability": 0.5, "instrumentalness": 0.5}


def test_check_expectations_pass_and_fail():
    result = FakeResult([song("lofi", 0.3), song("ambient", 0.2)])
    assert check_expectations({"top1_genre_in": ["lofi"], "avg_max": {"energy": 0.4}}, result, None) == []
    failures = check_expectations({"top1_genre_in": ["rock"], "min_results": 5,
                                   "none_genre": ["ambient"]}, result, None)
    assert len(failures) == 3


def test_check_expectations_rejections():
    error = GuardrailError("bad_k", "x")
    assert check_expectations({"rejected": "bad_k"}, None, error) == []
    assert check_expectations({"rejected": "bad_k"}, FakeResult([song()]), None)
    assert check_expectations({"top1_genre_in": ["pop"]}, None, error) == ["request was rejected (bad_k)"]


def test_full_evaluation_has_no_unexpected_failures():
    import os
    old = os.getcwd()
    os.chdir(ROOT)
    try:
        report = run_evaluation(build_workflow())
    finally:
        os.chdir(old)
    summary = report["summary"]
    assert summary["unexpected_failures"] == []
    assert summary["workflow"]["guardrail"]["passed"] == summary["workflow"]["guardrail"]["total"]
    # the workflow should beat the keyword-only baseline on quality cases
    assert summary["workflow"]["quality"]["passed"] > summary["baseline"]["quality"]["passed"]


def test_chart_is_valid_svg(tmp_path):
    summary = {"workflow": {"quality": {"passed": 3, "total": 4}, "edge": {"passed": 1, "total": 1},
                            "guardrail": {"passed": 2, "total": 2}},
               "baseline": {"quality": {"passed": 1, "total": 4}, "edge": {"passed": 0, "total": 1}}}
    path = tmp_path / "chart.svg"
    write_chart(summary, str(path))
    root = ET.parse(path).getroot()
    assert root.tag.endswith("svg")
    assert "3/4" in path.read_text(encoding="utf-8")
