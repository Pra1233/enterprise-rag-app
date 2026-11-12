"""Answer-quality evaluation: runs the EXISTING LangGraph RAG workflow
(src.retrieval.graph.run_rag_query — the same function the /chat API calls)
end to end and scores the result with RAGAS. Never reimplements retrieval or
generation for evaluation purposes.
"""

import logging
import time
from dataclasses import dataclass, field

from ragas.dataset_schema import SingleTurnSample

from src.evaluation.dataset import EvaluationCase
from src.evaluation.metrics import score_single_turn
from src.retrieval.graph import run_rag_query

logger = logging.getLogger(__name__)


@dataclass
class AnswerCaseResult:
    case_id: str
    question: str
    expects_refusal: bool = False
    generated_answer: str = ""
    is_relevant: bool = False
    iteration_count: int = 0
    # Only meaningful when expects_refusal is True.
    correctly_refused: bool | None = None
    citations: list[dict] = field(default_factory=list)
    # Only populated for non-refusal cases — see docstring below.
    scores: dict[str, float | None] = field(default_factory=dict)
    latency_seconds: float = 0.0
    error: str | None = None


async def evaluate_answer_case(case: EvaluationCase, tenant_id: str) -> AnswerCaseResult:
    """Run one question through the real RAG workflow and score the answer.

    For `expects_refusal` cases, the only thing checked is whether the system
    actually refused (`is_relevant is False` from the LangGraph state) — RAGAS
    faithfulness/relevancy are NOT computed, since there is no ground-truth
    answer to score a guess against, and scoring one would reward exactly the
    behavior (confidently answering from nothing) that's supposed to be wrong.
    """
    result = AnswerCaseResult(case_id=case.case_id, question=case.question, expects_refusal=case.expects_refusal)

    try:
        start = time.monotonic()
        state = await run_rag_query(case.question, tenant_id, case.metadata.get("document_type"))
        result.latency_seconds = time.monotonic() - start

        result.generated_answer = state["final_answer"]
        result.is_relevant = state["is_relevant"]
        result.iteration_count = state["iteration_count"]
        result.citations = [
            {"document_id": str(c.document_id), "chunk_id": str(c.chunk_id), "source_uri": c.source_uri}
            for c in state["reranked_docs"]
        ]

        if case.expects_refusal:
            result.correctly_refused = not result.is_relevant
            return result

        contexts = [c.content for c in state["reranked_docs"]] or [""]
        sample = SingleTurnSample(
            user_input=case.question,
            response=result.generated_answer,
            retrieved_contexts=contexts,
            reference=case.ground_truth,
        )
        result.scores = await score_single_turn(sample)

    except Exception as exc:
        logger.error("Answer evaluation failed for case '%s'", case.case_id, exc_info=True)
        result.error = str(exc)

    return result
