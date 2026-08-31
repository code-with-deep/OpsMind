"""OpsMind Offline Evaluation Runner (P7).

Executes golden evaluation dataset against the live or mocked OpsMind engine,
scores with multi-dimensional rubrics, and generates JSON + Markdown scorecards.

Usage:
    python -m evals.run
    python -m evals.run --category root_cause
    python -m evals.run --output-format markdown
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from evals.scorers import (
    score_adversarial_guardrails,
    score_citation_faithfulness,
    score_numeric_accuracy,
    score_status_and_abstention,
    score_theme_recall,
)
from evals.types import CaseEvalResult, GoldenCase, SuiteSummary
from api.app.config import get_settings
from opsmind.graph.runner import run_investigation


def load_golden_cases(cases_path: Path | str | None = None) -> list[GoldenCase]:
    """Load golden cases from JSONL dataset."""
    if cases_path is None:
        cases_path = Path(__file__).resolve().parent / "cases.jsonl"
    else:
        cases_path = Path(cases_path)

    if not cases_path.exists():
        raise FileNotFoundError(f"Evaluation cases file not found at {cases_path}")

    cases: list[GoldenCase] = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            data = json.loads(line)
            cases.append(GoldenCase.from_dict(data))
    return cases


def evaluate_single_case(
    case: GoldenCase,
    settings: Any,
    *,
    use_postgres_checkpoint: bool = False,
) -> CaseEvalResult:
    """Run an investigation for a single golden case and score its output."""
    t0 = time.perf_counter()

    # Pass tool budget override if defined on case
    runtime_overrides: dict[str, Any] = {}
    if case.max_tool_calls is not None:
        runtime_overrides["max_tool_calls_per_run"] = case.max_tool_calls

    errors: list[str] = []
    try:
        run_res = run_investigation(
            question=case.question,
            settings=settings,
            use_postgres_checkpoint=use_postgres_checkpoint,
            runtime_overrides=runtime_overrides if runtime_overrides else None,
        )
    except Exception as exc:
        run_res = {
            "status": "failed",
            "errors": [str(exc)],
            "recommendation": None,
            "hypothesis": None,
            "findings": [],
        }
        errors.append(str(exc))

    elapsed = time.perf_counter() - t0
    status = run_res.get("status", "unknown")

    # Calculate metric scores
    status_metric = score_status_and_abstention(case, run_res)
    faithfulness_metric = score_citation_faithfulness(case, run_res)
    theme_metric = score_theme_recall(case, run_res)
    numeric_metric = score_numeric_accuracy(
        case, run_res, database_url_readonly=settings.database_url_readonly
    )
    adversarial_metric = score_adversarial_guardrails(case, run_res)

    metrics = {
        "status_correctness": status_metric,
        "citation_faithfulness": faithfulness_metric,
        "theme_recall": theme_metric,
        "numeric_accuracy": numeric_metric,
        "adversarial_robustness": adversarial_metric,
    }

    # Case passes if all required metrics pass
    all_passed = all(m.passed for m in metrics.values())
    overall_score = sum(m.score for m in metrics.values()) / len(metrics)

    return CaseEvalResult(
        case_id=case.id,
        category=case.category,
        status=status,
        passed=all_passed,
        overall_score=overall_score,
        metrics=metrics,
        investigation_id=run_res.get("investigation_id"),
        duration_sec=elapsed,
        raw_output=run_res,
        errors=errors or list(run_res.get("errors") or []),
    )


def run_evaluation_suite(
    cases: list[GoldenCase],
    settings: Any | None = None,
    *,
    category: str | None = None,
    case_ids: list[str] | None = None,
    use_postgres_checkpoint: bool = False,
) -> SuiteSummary:
    """Run the evaluation suite over selected cases and aggregate results."""
    if settings is None:
        settings = get_settings()

    filtered_cases = cases
    if category:
        filtered_cases = [c for c in filtered_cases if c.category == category]
    if case_ids:
        filtered_cases = [c for c in filtered_cases if c.id in case_ids]

    results: list[CaseEvalResult] = []
    start_all = time.perf_counter()

    for c in filtered_cases:
        res = evaluate_single_case(
            c, settings, use_postgres_checkpoint=use_postgres_checkpoint
        )
        results.append(res)

    total_time = time.perf_counter() - start_all

    # Aggregate category statistics
    cat_scores: dict[str, list[float]] = {}
    cat_counts: dict[str, dict[str, int]] = {}

    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    for r in results:
        cat_scores.setdefault(r.category, []).append(r.overall_score)
        counts = cat_counts.setdefault(r.category, {"total": 0, "passed": 0, "failed": 0})
        counts["total"] += 1
        if r.passed:
            counts["passed"] += 1
        else:
            counts["failed"] += 1

    avg_score = sum(r.overall_score for r in results) / max(1, total_count)
    cat_averages = {
        cat: sum(scores) / max(1, len(scores)) for cat, scores in cat_scores.items()
    }

    return SuiteSummary(
        total_cases=total_count,
        passed_cases=passed_count,
        failed_cases=total_count - passed_count,
        average_score=avg_score,
        category_scores=cat_averages,
        category_counts=cat_counts,
        results=results,
        duration_total_sec=total_time,
    )


def generate_markdown_report(summary: SuiteSummary) -> str:
    """Generate a clean Markdown report scorecard."""
    pass_pct = (summary.passed_cases / max(1, summary.total_cases)) * 100
    avg_score_pct = summary.average_score * 100

    md = [
        "# OpsMind Evaluation Scorecard (Phase 7)",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Duration:** {summary.duration_total_sec:.2f}s  ",
        f"**Total Cases:** {summary.total_cases} | **Passed:** {summary.passed_cases} | **Failed:** {summary.failed_cases}  ",
        f"**Pass Rate:** {pass_pct:.1f}% | **Average Quality Score:** {avg_score_pct:.1f}%  ",
        "",
        "## Category Breakdown",
        "",
        "| Category | Cases | Passed | Pass Rate | Avg Score |",
        "|:---|:---:|:---:|:---:|:---:|",
    ]

    for cat, counts in sorted(summary.category_counts.items()):
        score = summary.category_scores.get(cat, 0.0) * 100
        crate = (counts["passed"] / max(1, counts["total"])) * 100
        md.append(
            f"| `{cat}` | {counts['total']} | {counts['passed']} | {crate:.1f}% | {score:.1f}% |"
        )

    md.extend([
        "",
        "## Detailed Case Results",
        "",
        "| Case ID | Category | Status | Result | Score | Duration | Key Detail |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---|",
    ])

    for r in summary.results:
        mark = "PASS" if r.passed else "FAIL"
        status_detail = r.metrics.get("status_correctness")
        detail_msg = status_detail.details if status_detail else ""
        md.append(
            f"| `{r.case_id}` | `{r.category}` | `{r.status}` | **{mark}** | {r.overall_score * 100:.1f}% | {r.duration_sec:.2f}s | {detail_msg} |"
        )

    md.append("")
    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpsMind Evaluation Runner (P7)")
    parser.add_argument("--cases", type=str, default=None, help="Path to golden cases jsonl")
    parser.add_argument("--category", type=str, default=None, help="Filter by evaluation category")
    parser.add_argument("--output-json", type=str, default=None, help="Save scorecard JSON to file")
    parser.add_argument("--output-md", type=str, default=None, help="Save scorecard Markdown to file")
    parser.add_argument(
        "--output-format",
        choices=["text", "json", "markdown"],
        default="markdown",
        help="Console output format",
    )
    args = parser.parse_args()

    cases = load_golden_cases(args.cases)
    settings = get_settings()

    print(f"Running OpsMind evaluation harness on {len(cases)} golden cases...")
    summary = run_evaluation_suite(cases, settings, category=args.category)

    md_report = generate_markdown_report(summary)
    json_report = json.dumps(summary.to_dict(), indent=2)

    if args.output_json:
        Path(args.output_json).write_text(json_report, encoding="utf-8")
        print(f"Saved JSON report to {args.output_json}")

    if args.output_md:
        Path(args.output_md).write_text(md_report, encoding="utf-8")
        print(f"Saved Markdown report to {args.output_md}")

    if args.output_format == "markdown":
        print("\n" + md_report)
    elif args.output_format == "json":
        print("\n" + json_report)
    else:
        print(
            f"Summary: {summary.passed_cases}/{summary.total_cases} passed (Avg Score: {summary.average_score * 100:.1f}%)"
        )

    return 0 if summary.failed_cases == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
