"""Evaluation report generation: JSON/CSV persistence, summary/comparison
reports, matplotlib charts, and baseline (regression) comparison.

Every number in these reports comes from an actual EvaluationRun — nothing
here fabricates or fills in a placeholder score.
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless — never tries to open a GUI window
import matplotlib.pyplot as plt
import pandas as pd

from src.core.config import get_settings
from src.evaluation.evaluator import EvaluationRun
from src.evaluation.retrieval_eval import summarize_retrieval_results

logger = logging.getLogger(__name__)

REGRESSION_THRESHOLD = 0.05  # a drop of more than 5 percentage points is flagged


# --- Raw persistence ---


def run_to_dict(run: EvaluationRun) -> dict[str, Any]:
    return {
        "dataset_name": run.dataset_name,
        "dataset_size": run.dataset_size,
        "tenant_id": run.tenant_id,
        "top_k": run.top_k,
        "strategies": list(run.strategies),
        "mode": run.mode,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "failed_case_ids": run.failed_case_ids,
        "retrieval_results": [asdict(r) for r in run.retrieval_results],
        "answer_results": [asdict(r) for r in run.answer_results],
    }


def save_json(run: EvaluationRun, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run_to_dict(run), indent=2, default=str), encoding="utf-8")
    return path


def _retrieval_dataframe(run: EvaluationRun) -> pd.DataFrame:
    rows = []
    for case_result in run.retrieval_results:
        for strategy_name, strategy in case_result.strategies.items():
            rows.append(
                {
                    "case_id": case_result.case_id,
                    "question": case_result.question,
                    "strategy": strategy_name,
                    "recall_at_k": strategy.recall_at_k,
                    "precision_at_k": strategy.precision_at_k,
                    "mrr": strategy.mrr,
                    "hit_rate_at_k": strategy.hit_rate_at_k,
                    "ndcg_at_k": strategy.ndcg_at_k,
                    "chunk_recall_at_k": strategy.chunk_recall_at_k,
                    "chunk_precision_at_k": strategy.chunk_precision_at_k,
                    "latency_seconds": strategy.latency_seconds,
                    "error": case_result.error,
                }
            )
    return pd.DataFrame(rows)


def _answer_dataframe(run: EvaluationRun) -> pd.DataFrame:
    rows = []
    for r in run.answer_results:
        rows.append(
            {
                "case_id": r.case_id,
                "question": r.question,
                "expects_refusal": r.expects_refusal,
                "correctly_refused": r.correctly_refused,
                "is_relevant": r.is_relevant,
                "faithfulness": r.scores.get("faithfulness"),
                "answer_relevancy": r.scores.get("answer_relevancy"),
                "context_precision": r.scores.get("context_precision"),
                "context_recall": r.scores.get("context_recall"),
                "latency_seconds": r.latency_seconds,
                "error": r.error,
            }
        )
    return pd.DataFrame(rows)


def save_csv(run: EvaluationRun, output_dir: str | Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    if run.retrieval_results:
        retrieval_path = output_dir / "retrieval_results.csv"
        _retrieval_dataframe(run).to_csv(retrieval_path, index=False)
        paths["retrieval_csv"] = retrieval_path

    if run.answer_results:
        answer_path = output_dir / "answer_results.csv"
        _answer_dataframe(run).to_csv(answer_path, index=False)
        paths["answer_csv"] = answer_path

    return paths


# --- Summary / comparison reports ---


def generate_summary_report(run: EvaluationRun) -> dict[str, Any]:
    settings = get_settings()
    successful = run.dataset_size - len(run.failed_case_ids)

    summary: dict[str, Any] = {
        "dataset_name": run.dataset_name,
        "dataset_size": run.dataset_size,
        "mode": run.mode,
        "top_k": run.top_k,
        "strategies": list(run.strategies),
        "tenant_id": run.tenant_id,
        "evaluation_date": run.finished_at,
        "llm_model": settings.groq_model,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "successful_cases": successful,
        "failed_cases": len(run.failed_case_ids),
        "failed_case_ids": run.failed_case_ids,
    }

    if run.retrieval_results:
        summary["retrieval_comparison"] = summarize_retrieval_results(run.retrieval_results)

    if run.answer_results:
        summary["answer_quality"] = generate_answer_quality_report(run)

    return summary


def generate_retrieval_comparison_report(run: EvaluationRun) -> dict[str, Any]:
    """Per-strategy mean metrics — the basis for judging whether hybrid search
    and/or reranking actually improve retrieval quality for this dataset.
    Makes no assumption about which strategy wins.
    """
    return summarize_retrieval_results(run.retrieval_results)


def generate_answer_quality_report(run: EvaluationRun) -> dict[str, Any]:
    non_refusal = [r for r in run.answer_results if not r.expects_refusal and r.error is None]
    refusal_cases = [r for r in run.answer_results if r.expects_refusal and r.error is None]

    def _mean_score(metric: str) -> float | None:
        values = [r.scores.get(metric) for r in non_refusal if r.scores.get(metric) is not None]
        return mean(values) if values else None

    report: dict[str, Any] = {
        "faithfulness": _mean_score("faithfulness"),
        "answer_relevancy": _mean_score("answer_relevancy"),
        "context_precision": _mean_score("context_precision"),
        "context_recall": _mean_score("context_recall"),
        "answerable_cases_evaluated": len(non_refusal),
    }

    if refusal_cases:
        correct = [r.correctly_refused for r in refusal_cases if r.correctly_refused is not None]
        report["refusal_accuracy"] = (sum(1 for c in correct if c) / len(correct)) if correct else None
        report["refusal_cases_evaluated"] = len(refusal_cases)

    return report


def generate_latency_report(run: EvaluationRun) -> dict[str, Any]:
    report: dict[str, Any] = {}

    if run.retrieval_results:
        retrieval_df = _retrieval_dataframe(run)
        if not retrieval_df.empty:
            report["retrieval_latency_by_strategy"] = {
                strategy: {
                    "mean_seconds": group["latency_seconds"].mean(),
                    "p95_seconds": group["latency_seconds"].quantile(0.95),
                }
                for strategy, group in retrieval_df.groupby("strategy")
            }

    if run.answer_results:
        latencies = [r.latency_seconds for r in run.answer_results if r.error is None]
        if latencies:
            series = pd.Series(latencies)
            report["end_to_end_latency_seconds"] = {
                "mean": series.mean(),
                "p95": series.quantile(0.95),
                "min": series.min(),
                "max": series.max(),
            }

    return report


# --- Charts ---


def generate_charts(run: EvaluationRun, output_dir: str | Path) -> list[Path]:
    output_dir = Path(output_dir) / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[Path] = []

    if run.answer_results:
        quality = generate_answer_quality_report(run)
        metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        values = [quality.get(m) for m in metric_names]
        if any(v is not None for v in values):
            path = output_dir / "answer_quality.png"
            _bar_chart(
                metric_names,
                [v if v is not None else 0.0 for v in values],
                title="Answer quality (RAGAS)",
                ylabel="Score (0-1)",
                path=path,
            )
            chart_paths.append(path)

    if run.retrieval_results:
        comparison = summarize_retrieval_results(run.retrieval_results)
        strategies = list(comparison.keys())

        for metric_name, title in [("recall_at_k", "Recall@K by strategy"), ("mrr", "MRR by strategy")]:
            values = [comparison[s].get(metric_name) for s in strategies]
            if any(v is not None for v in values):
                path = output_dir / f"{metric_name}.png"
                _bar_chart(
                    strategies,
                    [v if v is not None else 0.0 for v in values],
                    title=title,
                    ylabel=metric_name,
                    path=path,
                )
                chart_paths.append(path)

        latencies = [comparison[s].get("mean_latency_seconds") for s in strategies]
        if any(v is not None for v in latencies):
            path = output_dir / "retrieval_latency.png"
            _bar_chart(
                strategies,
                [v if v is not None else 0.0 for v in latencies],
                title="Mean retrieval latency by strategy",
                ylabel="Seconds",
                path=path,
            )
            chart_paths.append(path)

    if run.answer_results:
        latency_report = generate_latency_report(run)
        e2e = latency_report.get("end_to_end_latency_seconds")
        if e2e:
            path = output_dir / "end_to_end_latency.png"
            _bar_chart(
                ["mean", "p95"],
                [e2e["mean"], e2e["p95"]],
                title="End-to-end response latency",
                ylabel="Seconds",
                path=path,
            )
            chart_paths.append(path)

    return chart_paths


def _bar_chart(labels: list[str], values: list[float], title: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, values, color="#7c3aed")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# --- Baseline / regression comparison ---


def compare_to_baseline(current_summary: dict[str, Any], baseline_summary: dict[str, Any]) -> dict[str, Any]:
    """Per-metric deltas between the current run and a previous baseline.

    Deliberately does NOT emit a single "better/worse" verdict — retrieval
    quality, answer quality and latency must be weighed together, which
    requires human judgment the tool doesn't have. It only reports deltas and
    flags individually significant regressions (> REGRESSION_THRESHOLD drop).
    """
    comparison: dict[str, Any] = {"regressions": [], "improvements": [], "deltas": {}}

    def _compare_section(section: str, current: dict | None, baseline: dict | None) -> None:
        if not current or not baseline:
            return
        for key in set(current) | set(baseline):
            cur_val = current.get(key)
            if isinstance(cur_val, dict):
                _compare_section(f"{section}.{key}", cur_val, baseline.get(key) or {})
                continue
            base_val = baseline.get(key)
            if not isinstance(cur_val, (int, float)) or not isinstance(base_val, (int, float)):
                continue
            delta = cur_val - base_val
            path = f"{section}.{key}"
            comparison["deltas"][path] = {"current": cur_val, "baseline": base_val, "delta": delta}
            if delta <= -REGRESSION_THRESHOLD:
                comparison["regressions"].append(path)
            elif delta >= REGRESSION_THRESHOLD:
                comparison["improvements"].append(path)

    _compare_section(
        "retrieval_comparison",
        current_summary.get("retrieval_comparison"),
        baseline_summary.get("retrieval_comparison"),
    )
    _compare_section("answer_quality", current_summary.get("answer_quality"), baseline_summary.get("answer_quality"))

    comparison["note"] = (
        "Deltas only. Deciding whether this configuration is actually better requires weighing "
        "retrieval quality, answer quality, latency and resource consumption together — this report "
        "does not declare a winner."
    )
    return comparison


# --- Orchestration ---


def generate_all_reports(
    run: EvaluationRun, output_dir: str | Path, baseline_path: str | Path | None = None
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    paths["raw_json"] = str(save_json(run, output_dir / "run.json"))
    for label, path in save_csv(run, output_dir).items():
        paths[label] = str(path)

    summary = generate_summary_report(run)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    paths["summary"] = str(summary_path)

    latency_report = generate_latency_report(run)
    latency_path = output_dir / "latency_report.json"
    latency_path.write_text(json.dumps(latency_report, indent=2, default=str), encoding="utf-8")
    paths["latency_report"] = str(latency_path)

    for chart_path in generate_charts(run, output_dir):
        paths[f"chart:{chart_path.stem}"] = str(chart_path)

    if baseline_path:
        baseline_summary = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        comparison = compare_to_baseline(summary, baseline_summary)
        comparison_path = output_dir / "baseline_comparison.json"
        comparison_path.write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")
        paths["baseline_comparison"] = str(comparison_path)

    return paths
