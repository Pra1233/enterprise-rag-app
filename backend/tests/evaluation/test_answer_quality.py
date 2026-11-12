from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.evaluation.answer_eval import evaluate_answer_case
from src.evaluation.dataset import EvaluationCase
from src.evaluation.metrics import score_single_turn
from src.models.okf import DocumentType, RetrievedChunk


def _fake_chunk(content: str = "Project Aurora is led by Dr. Vasquez.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        parent_doc_id=uuid4(),
        content=content,
        document_id=uuid4(),
        tenant_id="eval-tenant",
        source_uri="eval-tenant/doc.pdf",
        document_type=DocumentType.PDF,
        author=None,
        page_numbers=[0],
        score=0.9,
        rerank_score=0.95,
    )


def _fake_rag_state(answer: str, is_relevant: bool, chunks=None):
    return {
        "final_answer": answer,
        "is_relevant": is_relevant,
        "iteration_count": 0,
        "reranked_docs": chunks or [],
    }


# --- 7. Faithfulness evaluation / 8. Answer relevancy evaluation (mocked LLM) ---


@pytest.mark.asyncio
async def test_score_single_turn_returns_all_requested_metrics(monkeypatch):
    class FakeMetric:
        def __init__(self, value):
            self.value = value

        async def single_turn_ascore(self, sample):
            return self.value

    fake_metrics = {
        "faithfulness": FakeMetric(0.92),
        "answer_relevancy": FakeMetric(0.87),
        "context_precision": FakeMetric(0.75),
        "context_recall": FakeMetric(0.80),
    }
    monkeypatch.setattr("src.evaluation.metrics.get_ragas_metrics", lambda: fake_metrics)

    scores = await score_single_turn(sample=object())

    assert scores == {"faithfulness": 0.92, "answer_relevancy": 0.87, "context_precision": 0.75, "context_recall": 0.80}


@pytest.mark.asyncio
async def test_score_single_turn_isolates_a_failing_metric(monkeypatch):
    class OkMetric:
        async def single_turn_ascore(self, sample):
            return 0.5

    class BrokenMetric:
        async def single_turn_ascore(self, sample):
            raise RuntimeError("Groq rate limit exceeded")

    monkeypatch.setattr(
        "src.evaluation.metrics.get_ragas_metrics",
        lambda: {"faithfulness": OkMetric(), "answer_relevancy": BrokenMetric()},
    )

    scores = await score_single_turn(sample=object())

    assert scores["faithfulness"] == 0.5
    assert scores["answer_relevancy"] is None  # failure isolated, not propagated


@pytest.mark.asyncio
async def test_evaluate_answer_case_scores_an_answerable_question(monkeypatch):
    chunk = _fake_chunk()
    state = _fake_rag_state("Dr. Vasquez leads Project Aurora.", is_relevant=True, chunks=[chunk])
    monkeypatch.setattr("src.evaluation.answer_eval.run_rag_query", AsyncMock(return_value=state))
    fake_scores = {"faithfulness": 1.0, "answer_relevancy": 0.95, "context_precision": 0.9, "context_recall": 0.9}
    monkeypatch.setattr("src.evaluation.answer_eval.score_single_turn", AsyncMock(return_value=fake_scores))

    case = EvaluationCase(question="Who leads Project Aurora?", ground_truth="Dr. Vasquez leads it.")
    result = await evaluate_answer_case(case, tenant_id="eval-tenant")

    assert result.error is None
    assert result.generated_answer == state["final_answer"]
    assert result.scores["faithfulness"] == 1.0
    assert len(result.citations) == 1
    assert result.citations[0]["chunk_id"] == str(chunk.chunk_id)


# --- Refusal-expected cases: correctness is NOT rewarding a guess ---


@pytest.mark.asyncio
async def test_refusal_case_marked_correct_when_system_actually_refuses(monkeypatch):
    state = _fake_rag_state(
        "I couldn't find reliable information in the knowledge base to answer this question confidently.",
        is_relevant=False,
    )
    monkeypatch.setattr("src.evaluation.answer_eval.run_rag_query", AsyncMock(return_value=state))
    score_mock = AsyncMock()
    monkeypatch.setattr("src.evaluation.answer_eval.score_single_turn", score_mock)

    case = EvaluationCase(
        question="What was our competitor's revenue?",
        ground_truth="Not available internally.",
        expects_refusal=True,
    )
    result = await evaluate_answer_case(case, tenant_id="eval-tenant")

    assert result.correctly_refused is True
    score_mock.assert_not_called()  # never scores a non-existent "guess" with RAGAS


@pytest.mark.asyncio
async def test_refusal_case_marked_incorrect_when_system_guesses_instead(monkeypatch):
    """The system hallucinating an answer when it should have refused must NOT be rewarded."""
    state = _fake_rag_state("Our competitor's revenue was 10 crore.", is_relevant=True, chunks=[_fake_chunk()])
    monkeypatch.setattr("src.evaluation.answer_eval.run_rag_query", AsyncMock(return_value=state))

    case = EvaluationCase(
        question="What was our competitor's revenue?",
        ground_truth="Not available internally.",
        expects_refusal=True,
    )
    result = await evaluate_answer_case(case, tenant_id="eval-tenant")

    assert result.correctly_refused is False


# --- 9. Failed LLM requests ---


@pytest.mark.asyncio
async def test_evaluate_answer_case_records_failure_without_raising(monkeypatch):
    async def _raise(*args, **kwargs):
        raise RuntimeError("Groq API unavailable")

    monkeypatch.setattr("src.evaluation.answer_eval.run_rag_query", _raise)

    case = EvaluationCase(question="Q?", ground_truth="A.")
    result = await evaluate_answer_case(case, tenant_id="eval-tenant")

    assert result.error == "Groq API unavailable"
    assert result.scores == {}
