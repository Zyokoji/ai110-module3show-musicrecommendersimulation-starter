"""
VibeMatch command line app: plain-English requests in, explained recommendations out.

Examples (run from the project root):
    python -m src.app "calm lofi for studying"
    python -m src.app "intense rock for the gym" --trace
    python -m src.app "upbeat 90s jazz but no lofi" -k 3 --mode mood-first
    python -m src.app "k-pop dance hits" --compare       # workflow vs keyword-only baseline
    python -m src.app                                    # interactive prompt

The Module 3 profile CLI still works:  python -m src.main
"""

import argparse
import json
import sys
from typing import List

from src.guardrails import GuardrailError
from src.logging_setup import setup_logging
from src.main import format_table, recommendation_table
from src.recommender import SCORING_MODES
from src.workflow import RecommendationWorkflow, WorkflowResult, build_workflow


def format_prefs(prefs: dict) -> str:
    """Readable one-line version of the preferences the workflow used."""
    return ", ".join(f"{key}={value}" for key, value in prefs.items()) or "(none)"


def print_result(result: WorkflowResult, show_trace: bool = False) -> None:
    """Print the interpretation, warnings, recommendation table and (optionally) the trace."""
    kind = "AI workflow (retrieval + self-check)" if result.use_retrieval else "Baseline (keywords only)"
    print(f"\n=== {kind} ===")
    print(f"Request    : {result.query}")
    print(f"Context    : {result.context or '(none matched)'}")
    print(f"Using      : {format_prefs(result.prefs)}")
    print(f"Confidence : {result.confidence:.2f} ({result.confidence_label})")
    for warning in result.warnings:
        print(f"Note       : {warning}")
    if result.recommendations:
        print(recommendation_table(result.recommendations))
        print("Summary:")
        for rank, rec in enumerate(result.recommendations, start=1):
            print(f"  {rank}. {rec['song']['title']}: {rec['summary']}")
    else:
        print("No songs matched this request.")
    if show_trace:
        print("\nWorkflow trace:")
        for number, step in enumerate(result.trace, start=1):
            print(f"  {number}. {step.step:<12} -> {step.decision}")
            for key, value in step.details.items():
                print(f"       {key}: {json.dumps(value, default=str)}")


def print_comparison(workflow_result: WorkflowResult, baseline_result) -> None:
    """Side-by-side top-k titles for workflow vs baseline."""
    base_recs = baseline_result.recommendations if baseline_result else []
    rows: List[list] = []
    for i in range(max(len(workflow_result.recommendations), len(base_recs), 1)):
        def cell(recs):
            return f"{recs[i]['song']['title']} ({recs[i]['song']['genre']})" if i < len(recs) else "-"
        rows.append([i + 1, cell(workflow_result.recommendations), cell(base_recs)])
    print("\n--- Workflow vs baseline ---")
    print(format_table(["#", "AI workflow", "Baseline (keywords only)"], rows, [2, 34, 34]))


def run_once(workflow: RecommendationWorkflow, query: str, args) -> int:
    """Handle one request; returns a process exit code (0 ok, 2 rejected)."""
    diversity = not args.no_diversity
    try:
        result = workflow.run(query, k=args.k, mode=args.mode, diversity=diversity,
                              use_retrieval=not args.baseline)
    except GuardrailError as error:
        print(f"Request rejected ({error.code}): {error.message}")
        return 2
    print_result(result, args.trace)
    if args.compare and not args.baseline:
        try:
            baseline = workflow.run(query, k=args.k, mode=args.mode, diversity=diversity,
                                    use_retrieval=False)
        except GuardrailError as error:
            print(f"\nBaseline could not handle this request ({error.code}): {error.message}")
            baseline = None
        print_comparison(result, baseline)
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    """Read command line options."""
    parser = argparse.ArgumentParser(description="VibeMatch: explainable music recommendations")
    parser.add_argument("query", nargs="?", help="what you want to listen to (omit for interactive mode)")
    parser.add_argument("-k", type=int, default=5, help="number of songs (1-20, default 5)")
    parser.add_argument("--mode", default="balanced", choices=list(SCORING_MODES))
    parser.add_argument("--no-diversity", action="store_true", help="turn off the diversity penalty")
    parser.add_argument("--trace", action="store_true", help="show every workflow step and decision")
    parser.add_argument("--baseline", action="store_true", help="run the keyword-only baseline instead")
    parser.add_argument("--compare", action="store_true", help="also show the baseline side by side")
    parser.add_argument("--verbose", action="store_true", help="print INFO log messages to the terminal")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """Entry point: load data, then answer one request or start an interactive loop."""
    args = parse_args(argv)
    setup_logging(args.verbose)
    try:
        workflow = build_workflow()
    except (FileNotFoundError, OSError) as error:
        print(f"Could not start: {error}")
        return 1
    print(f"Loaded {len(workflow.songs)} songs and {len(workflow.knowledge.activities)} activity contexts.")

    if args.query is not None:
        return run_once(workflow, args.query, args)

    print("Type what you want to hear (empty line or 'quit' to exit).")
    while True:
        try:
            query = input("\nVibeMatch> ").strip()
        except EOFError:
            break
        if query.lower() in {"", "quit", "exit"}:
            break
        run_once(workflow, query, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
