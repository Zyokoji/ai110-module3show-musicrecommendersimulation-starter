"""
Evaluation harness for VibeMatch.

Runs every case in evaluation/cases.json, checks the expectations, and prints a
pass/fail report comparing the AI workflow with the keyword-only baseline.

    python -m evaluation.run_eval            # report + save results + chart
    python -m evaluation.run_eval --quiet    # summary only

Outputs:
    evaluation/results.json     machine-readable results of the last run
    assets/eval_results.svg     bar chart of pass counts (no plotting library needed)
Exit code is 1 if any workflow case fails that is not marked as a documented
known_limitation in cases.json, so it can be used in CI.
"""

import argparse
import json
import os
import sys
from statistics import mean
from typing import Dict, List, Optional

from src.guardrails import GuardrailError
from src.logging_setup import setup_logging
from src.main import format_table
from src.workflow import RecommendationWorkflow, WorkflowResult, build_workflow

CASES_PATH = os.path.join("evaluation", "cases.json")
RESULTS_PATH = os.path.join("evaluation", "results.json")
CHART_PATH = os.path.join("assets", "eval_results.svg")


def check_expectations(expect: Dict, result: Optional[WorkflowResult],
                       error: Optional[GuardrailError]) -> List[str]:
    """Return a list of failed checks (empty list = the case passed)."""
    failures: List[str] = []
    if "rejected" in expect:
        if error is None:
            return [f"expected rejection '{expect['rejected']}' but the request was accepted"]
        if error.code != expect["rejected"]:
            return [f"rejected with '{error.code}' instead of '{expect['rejected']}'"]
        return []
    if error is not None:
        return [f"request was rejected ({error.code})"]

    recs = result.recommendations
    songs = [r["song"] for r in recs]
    if not songs:
        return ["no recommendations returned"]

    def average(feature):
        return mean(s[feature] for s in songs)

    if "top1_genre_in" in expect and songs[0]["genre"] not in expect["top1_genre_in"]:
        failures.append(f"top song genre is {songs[0]['genre']}, expected {expect['top1_genre_in']}")
    for feature, limit in expect.get("avg_max", {}).items():
        if average(feature) > limit:
            failures.append(f"average {feature} {average(feature):.2f} > {limit}")
    for feature, limit in expect.get("avg_min", {}).items():
        if average(feature) < limit:
            failures.append(f"average {feature} {average(feature):.2f} < {limit}")
    if "min_genre_count" in expect:
        rule = expect["min_genre_count"]
        count = sum(1 for s in songs if s["genre"] in rule["genres"])
        if count < rule["count"]:
            failures.append(f"only {count} songs from {rule['genres']} (need {rule['count']})")
    if "none_genre" in expect:
        found = [s["title"] for s in songs if s["genre"] in expect["none_genre"]]
        if found:
            failures.append(f"excluded genre present: {found}")
    if "min_results" in expect and len(songs) < expect["min_results"]:
        failures.append(f"{len(songs)} results, expected at least {expect['min_results']}")
    if "confidence_in" in expect and result.confidence_label not in expect["confidence_in"]:
        failures.append(f"confidence {result.confidence_label}, expected {expect['confidence_in']}")
    if "warning_contains" in expect and not any(expect["warning_contains"] in w for w in result.warnings):
        failures.append(f"no warning containing '{expect['warning_contains']}'")
    if "each_top3_mood_or_tag" in expect:
        rule = expect["each_top3_mood_or_tag"]
        for s in songs[:3]:
            if s["mood"] not in rule["moods"] and not set(s["mood_tags"]) & set(rule["tags"]):
                failures.append(f"{s['title']} has neither a wanted mood nor tag")
    return failures


def run_case(workflow: RecommendationWorkflow, case: Dict, defaults: Dict, use_retrieval: bool) -> Dict:
    """Run one case in one system and return a result record."""
    result, error = None, None
    try:
        result = workflow.run(case["query"], k=case.get("k", defaults["k"]),
                              mode=case.get("mode", defaults["mode"]),
                              diversity=case.get("diversity", defaults["diversity"]),
                              use_retrieval=use_retrieval)
    except GuardrailError as caught:
        error = caught
    failures = check_expectations(case["expect"], result, error)
    return {
        "passed": not failures,
        "failures": failures,
        "rejected": error.code if error else None,
        "confidence": result.confidence if result else None,
        "top": [r["song"]["title"] for r in result.recommendations] if result else [],
    }


def run_evaluation(workflow: RecommendationWorkflow, cases_path: str = CASES_PATH) -> Dict:
    """Run all cases for the workflow (and the baseline where meaningful)."""
    with open(cases_path, encoding="utf-8") as handle:
        spec = json.load(handle)
    rows = []
    for case in spec["cases"]:
        row = {"id": case["id"], "category": case["category"], "query": case["query"][:60],
               "known_limitation": case.get("known_limitation"),
               "workflow": run_case(workflow, case, spec["defaults"], use_retrieval=True)}
        if case["category"] != "guardrail":  # validation is shared, so baseline adds nothing there
            row["baseline"] = run_case(workflow, case, spec["defaults"], use_retrieval=False)
        rows.append(row)

    def tally(system, categories):
        relevant = [r for r in rows if r["category"] in categories and system in r]
        return {"passed": sum(r[system]["passed"] for r in relevant), "total": len(relevant)}

    categories = ["quality", "edge", "guardrail"]
    confidences = [r["workflow"]["confidence"] for r in rows if r["workflow"]["confidence"] is not None]
    summary = {
        "workflow": {c: tally("workflow", [c]) for c in categories},
        "baseline": {c: tally("baseline", [c]) for c in categories if c != "guardrail"},
        "workflow_all": tally("workflow", categories),
        "unexpected_failures": [r["id"] for r in rows
                                if not r["workflow"]["passed"] and not r["known_limitation"]],
        "known_limitation_failures": [r["id"] for r in rows
                                      if not r["workflow"]["passed"] and r["known_limitation"]],
        "average_confidence": round(mean(confidences), 2) if confidences else None,
    }
    return {"rows": rows, "summary": summary}


def write_chart(summary: Dict, path: str = CHART_PATH) -> None:
    """Write a simple grouped bar chart (SVG) of pass rates per category."""
    groups = [("quality", "Quality"), ("edge", "Edge cases"), ("guardrail", "Guardrails")]
    width, height, left, bottom, bar = 560, 300, 60, 250, 48
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'font-family="Arial, sans-serif" font-size="12">',
             f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
             '<text x="280" y="22" text-anchor="middle" font-size="15" font-weight="bold">'
             'VibeMatch evaluation: cases passed</text>',
             f'<line x1="{left}" y1="{bottom}" x2="{width - 20}" y2="{bottom}" stroke="#444"/>']
    for pct in (0, 50, 100):
        y = bottom - pct * 2
        parts.append(f'<text x="{left - 8}" y="{y + 4}" text-anchor="end" fill="#555">{pct}%</text>')
        parts.append(f'<line x1="{left}" y1="{y}" x2="{width - 20}" y2="{y}" stroke="#ddd"/>')
    colors = {"workflow": "#2f6fb0", "baseline": "#c9852b"}
    for index, (key, label) in enumerate(groups):
        x0 = left + 30 + index * 160
        for offset, system in enumerate(["workflow", "baseline"]):
            stats = summary[system].get(key)
            if not stats or not stats["total"]:
                continue
            rate = stats["passed"] / stats["total"]
            h = rate * 200
            x = x0 + offset * (bar + 6)
            parts.append(f'<rect x="{x}" y="{bottom - h:.1f}" width="{bar}" height="{h:.1f}" '
                         f'fill="{colors[system]}"/>')
            parts.append(f'<text x="{x + bar / 2}" y="{bottom - h - 6:.1f}" text-anchor="middle">'
                         f'{stats["passed"]}/{stats["total"]}</text>')
        parts.append(f'<text x="{x0 + bar}" y="{bottom + 18}" text-anchor="middle">{label}</text>')
    parts += [f'<rect x="{left}" y="270" width="12" height="12" fill="{colors["workflow"]}"/>',
              f'<text x="{left + 18}" y="281">AI workflow (retrieval + self-check)</text>',
              f'<rect x="{left + 250}" y="270" width="12" height="12" fill="{colors["baseline"]}"/>',
              f'<text x="{left + 268}" y="281">Keyword-only baseline</text>', '</svg>']
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts) + "\n")


def print_report(report: Dict, quiet: bool = False) -> None:
    """Print the per-case table and the summary."""
    def cell(record):
        if record is None:
            return "-"
        return "PASS" if record["passed"] else "FAIL: " + "; ".join(record["failures"])

    if not quiet:
        rows = [[r["id"], r["category"], r["query"] or "(empty)", cell(r["workflow"]), cell(r.get("baseline"))]
                for r in report["rows"]]
        print(format_table(["ID", "Type", "Request", "AI workflow", "Baseline"], rows, [3, 9, 28, 30, 30]))
    s = report["summary"]
    print("\nSummary")
    for category in ["quality", "edge", "guardrail"]:
        w = s["workflow"][category]
        b = s["baseline"].get(category)
        line = f"  {category:<9} AI workflow {w['passed']}/{w['total']}"
        if b:
            line += f"   baseline {b['passed']}/{b['total']}"
        print(line)
    total = s["workflow_all"]
    print(f"  overall   AI workflow {total['passed']}/{total['total']} passed; "
          f"average confidence on accepted requests: {s['average_confidence']}")
    for row in report["rows"]:
        if row["known_limitation"] and not row["workflow"]["passed"]:
            print(f"  known limitation {row['id']}: {row['known_limitation']}")
    if s["unexpected_failures"]:
        print(f"  UNEXPECTED FAILURES: {', '.join(s['unexpected_failures'])}")


def main(argv=None) -> int:
    """Run the evaluation, print the report, save results and chart."""
    parser = argparse.ArgumentParser(description="Run the VibeMatch evaluation cases")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    parser.add_argument("--no-save", action="store_true", help="do not write results.json or the chart")
    args = parser.parse_args(argv)
    setup_logging(verbose=False)
    workflow = build_workflow()
    report = run_evaluation(workflow)
    print_report(report, args.quiet)
    if not args.no_save:
        with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        write_chart(report["summary"])
        print(f"\nSaved {RESULTS_PATH} and {CHART_PATH}")
    return 1 if report["summary"]["unexpected_failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
