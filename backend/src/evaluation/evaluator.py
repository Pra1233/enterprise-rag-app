"""Orchestrates a full (or partial) evaluation run over an EvaluationDataset:
retrieval-only, answer-only, or both. Bounds concurrency so a run never
exceeds Groq's rate limits or saturates local CPU (embeddings/reranker).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.evaluation.answer_eval import AnswerCaseResult, evaluate_answer_case
from src.evaluation.dataset import EvaluationCase, EvaluationDataset
from src.evaluation.retrieval_eval import RETRIEVAL_STRATEGIES, RetrievalCaseResult, evaluate_retrieval_case

logger = logging.getLogger(__name__)

EvaluationMode = str  # "retrieval" | "answer" | "full"


@dataclass
class EvaluationRun:
    dataset_name: str
    dataset_size: int
    tenant_id: str
    top_k: int
    strategies: tuple[str, ...]
    mode: EvaluationMode
    started_at: str
    finished_at: str | None = None
    retrieval_results: list[RetrievalCaseResult] = field(default_factory=list)
    answer_results: list[AnswerCaseResult] = field(default_factory=list)
    # Failed cases are tracked explicitly here — never silently dropped from the run.
    failed_case_ids: list[str] = field(default_factory=list)


async def run_evaluation(
    dataset: EvaluationDataset,
    tenant_id: str,
    mode: EvaluationMode = "full",
    top_k: int = 5,
    strategies: tuple[str, ...] = RETRIEVAL_STRATEGIES,
    max_concurrency: int = 2,
) -> EvaluationRun:
    if mode not in ("retrieval", "answer", "full"):
        raise ValueError(f"Unknown evaluation mode '{mode}' (expected retrieval/answer/full)")

    run = EvaluationRun(
        dataset_name=dataset.name,
        dataset_size=len(dataset.cases),
        tenant_id=tenant_id,
        top_k=top_k,
        strategies=strategies,
        mode=mode,
        started_at=datetime.now(UTC).isoformat(),
    )

    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(case: EvaluationCase) -> None:
        async with semaphore:
            try:
                if mode in ("retrieval", "full"):
                    # Retrieval is local CPU work (embeddings + Qdrant), not
                    # Groq-rate-limited, but still goes through the same
                    # semaphore to cap total concurrent resource usage.
                    retrieval_result = await asyncio.to_thread(
                        evaluate_retrieval_case, case, tenant_id, top_k, top_k, strategies
                    )
                    run.retrieval_results.append(retrieval_result)
                    if retrieval_result.error:
                        run.failed_case_ids.append(case.case_id)

                if mode in ("answer", "full"):
                    answer_result = await evaluate_answer_case(case, tenant_id)
                    run.answer_results.append(answer_result)
                    if answer_result.error:
                        run.failed_case_ids.append(case.case_id)

            except Exception:
                logger.error("Unhandled failure evaluating case '%s'", case.case_id, exc_info=True)
                run.failed_case_ids.append(case.case_id)

    await asyncio.gather(*(run_one(case) for case in dataset.cases))

    run.failed_case_ids = sorted(set(run.failed_case_ids))
    run.finished_at = datetime.now(UTC).isoformat()
    return run
