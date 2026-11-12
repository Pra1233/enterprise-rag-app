import json
import os

import pytest

from src.evaluation.answer_eval import AnswerCaseResult
from src.evaluation.dataset import EvaluationCase, EvaluationDataset
from src.evaluation.evaluator import run_evaluation
from src.evaluation.reports import compare_to_baseline, generate_summary_report, save_csv, save_json
from src.evaluation.retrieval_eval import RetrievalCaseResult, StrategyResult


def _tiny_dataset() -> EvaluationDataset:
    return EvaluationDataset(
        name="tiny",
        cases=[
            EvaluationCase(case_id="c1", question="Q1?", ground_truth="A1.", expected_document_ids=["doc-1"]),
            EvaluationCase(case_id="c2", question="Q2?", ground_truth="A2.", expected_document_ids=["doc-2"]),
        ],
    )


# --- 10. Evaluation result persistence ---


def _fake_run_with_results():
    from src.evaluation.evaluator import EvaluationRun

    retrieval_result = RetrievalCaseResult(
        case_id="c1",
        question="Q1?",
        top_k=5,
        strategies={
            "dense": StrategyResult(
                strategy="dense",
                retrieved_document_ids=["doc-1"],
                retrieved_chunk_ids=["chunk-1"],
                latency_seconds=0.12,
                recall_at_k=1.0,
                precision_at_k=1.0,
                mrr=1.0,
                hit_rate_at_k=1.0,
                ndcg_at_k=1.0,
            )
        },
    )
    answer_result = AnswerCaseResult(
        case_id="c1",
        question="Q1?",
        generated_answer="A1.",
        is_relevant=True,
        scores={"faithfulness": 0.9, "answer_relevancy": 0.85, "context_precision": 0.8, "context_recall": 0.8},
        latency_seconds=1.5,
    )
    return EvaluationRun(
        dataset_name="tiny",
        dataset_size=2,
        tenant_id="eval-tenant",
        top_k=5,
        strategies=("dense",),
        mode="full",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:05+00:00",
        retrieval_results=[retrieval_result],
        answer_results=[answer_result],
        failed_case_ids=["c2"],
    )


def test_save_json_persists_full_run(tmp_path):
    run = _fake_run_with_results()
    path = save_json(run, tmp_path / "run.json")

    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["dataset_name"] == "tiny"
    assert loaded["failed_case_ids"] == ["c2"]
    assert loaded["retrieval_results"][0]["strategies"]["dense"]["recall_at_k"] == 1.0


def test_save_csv_persists_retrieval_and_answer_results(tmp_path):
    run = _fake_run_with_results()
    paths = save_csv(run, tmp_path)

    assert paths["retrieval_csv"].exists()
    assert paths["answer_csv"].exists()
    assert "dense" in paths["retrieval_csv"].read_text()
    assert "0.9" in paths["answer_csv"].read_text()


def test_summary_report_never_fabricates_missing_scores():
    run = _fake_run_with_results()
    summary = generate_summary_report(run)

    assert summary["dataset_size"] == 2
    assert summary["successful_cases"] == 1
    assert summary["failed_cases"] == 1
    assert summary["retrieval_comparison"]["dense"]["recall_at_k"] == 1.0
    assert summary["answer_quality"]["faithfulness"] == 0.9


# --- 11. Baseline comparison ---


def test_compare_to_baseline_flags_regression():
    # faithfulness drops by 0.25 (a real regression); answer_relevancy only moves
    # by 0.02, which is below the significance threshold and should be flagged as neither.
    current = {"answer_quality": {"faithfulness": 0.70, "answer_relevancy": 0.90}}
    baseline = {"answer_quality": {"faithfulness": 0.95, "answer_relevancy": 0.88}}

    comparison = compare_to_baseline(current, baseline)

    assert "answer_quality.faithfulness" in comparison["regressions"]
    assert comparison["deltas"]["answer_quality.faithfulness"]["delta"] == pytest.approx(-0.25)
    assert "answer_quality.answer_relevancy" not in comparison["regressions"]
    assert "answer_quality.answer_relevancy" not in comparison["improvements"]


def test_compare_to_baseline_never_declares_a_single_winner():
    current = {"answer_quality": {"faithfulness": 0.99}}
    baseline = {"answer_quality": {"faithfulness": 0.50}}

    comparison = compare_to_baseline(current, baseline)

    # No boolean "is_better" field — deltas + a note requiring human judgment, by design.
    assert "is_better" not in comparison
    assert "note" in comparison
    assert "answer_quality.faithfulness" in comparison["improvements"]


def test_compare_to_baseline_handles_missing_sections_gracefully():
    comparison = compare_to_baseline({"answer_quality": {"faithfulness": 0.9}}, {})
    assert comparison["regressions"] == []
    assert comparison["improvements"] == []


# --- 12. LangSmith configuration ---


def test_configure_langsmith_sets_env_vars_when_enabled(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-bytes-long-enough")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "rag-production-test")

    from src.core.config import get_settings

    get_settings.cache_clear()
    from src.observability.langsmith import configure_langsmith

    configure_langsmith()

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "rag-production-test"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"  # back-compat name also set
    assert os.environ["LANGCHAIN_PROJECT"] == "rag-production-test"
    get_settings.cache_clear()


def test_configure_langsmith_disabled_by_default(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-bytes-long-enough")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

    from src.core.config import get_settings

    get_settings.cache_clear()
    from src.observability.langsmith import configure_langsmith

    configure_langsmith()

    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    get_settings.cache_clear()


def test_build_trace_config_includes_required_metadata():
    from src.observability.tracing import build_trace_config

    config = build_trace_config(
        request_id="req-1", conversation_id="conv-1", tenant_id="tenant-1", retrieval_strategy="hybrid_rerank"
    )

    assert config["metadata"]["request_id"] == "req-1"
    assert config["metadata"]["conversation_id"] == "conv-1"
    assert config["metadata"]["tenant_id"] == "tenant-1"
    assert config["metadata"]["retrieval_strategy"] == "hybrid_rerank"
    assert "hybrid_rerank" in config["tags"]


# --- Evaluation runner orchestration (isolates failures, bounds concurrency) ---


async def test_run_evaluation_isolates_a_failing_case(monkeypatch):
    dataset = _tiny_dataset()

    async def fake_answer_eval(case, tenant_id):
        if case.case_id == "c2":
            raise RuntimeError("boom")
        return AnswerCaseResult(case_id=case.case_id, question=case.question, generated_answer="ok")

    monkeypatch.setattr("src.evaluation.evaluator.evaluate_answer_case", fake_answer_eval)

    run = await run_evaluation(dataset, tenant_id="eval-tenant", mode="answer", max_concurrency=2)

    assert len(run.answer_results) == 1  # c1 succeeded
    assert run.failed_case_ids == ["c2"]  # c2's failure is recorded, not silently dropped


async def test_run_evaluation_respects_max_concurrency(monkeypatch):
    dataset = EvaluationDataset(
        name="concurrency-test",
        cases=[EvaluationCase(question=f"Q{i}?", ground_truth="A.") for i in range(6)],
    )

    in_flight = 0
    max_observed = 0

    async def fake_answer_eval(case, tenant_id):
        nonlocal in_flight, max_observed
        in_flight += 1
        max_observed = max(max_observed, in_flight)
        import asyncio

        await asyncio.sleep(0.01)
        in_flight -= 1
        return AnswerCaseResult(case_id=case.case_id, question=case.question, generated_answer="ok")

    monkeypatch.setattr("src.evaluation.evaluator.evaluate_answer_case", fake_answer_eval)

    await run_evaluation(dataset, tenant_id="eval-tenant", mode="answer", max_concurrency=2)

    assert max_observed <= 2
