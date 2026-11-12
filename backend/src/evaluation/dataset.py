"""Pydantic models for the RAG evaluation dataset. Strict by design (OKF-style
— see src/models/okf.py) so a malformed dataset file fails fast at load time
instead of producing silently-wrong evaluation numbers.

This is evaluation-only data: it is never written by, or read by, the
production ingestion/retrieval pipeline. Keeping it a separate module (rather
than reusing src/models/okf.py) is deliberate — see dataset_loader.py.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCase(BaseModel):
    """One evaluation question plus everything needed to score an answer against it.

    `expected_document_ids` drives document-level retrieval metrics (Recall@K,
    Precision@K, MRR, NDCG@K). `expected_chunk_ids` is optional and, only when
    present, additionally drives chunk-level retrieval metrics — the two are
    never conflated (see evaluation/metrics.py).
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default_factory=lambda: str(uuid4()))
    question: str = Field(..., min_length=1)

    # Required even for refusal cases (see expects_refusal) — for those, it
    # should describe why the question is unanswerable, not a guessed fact.
    ground_truth: str = Field(..., min_length=1)
    ground_truth_contexts: list[str] = Field(default_factory=list)

    expected_document_ids: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] | None = Field(
        default=None, description="Optional: only set this if you have real chunk-level ground truth."
    )
    expected_source_references: list[str] = Field(default_factory=list)

    metadata: dict[str, str] = Field(default_factory=dict)

    # When true, the only correct behavior is for the RAG pipeline to refuse
    # to answer (grade_context's is_relevant == False) because the knowledge
    # base genuinely doesn't contain the answer. RAGAS faithfulness/relevancy
    # don't apply here — see evaluation/answer_eval.py.
    expects_refusal: bool = False


class EvaluationDataset(BaseModel):
    """A named, versioned collection of evaluation cases."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    version: str = "1.0.0"
    cases: list[EvaluationCase] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _unique_case_ids(self) -> "EvaluationDataset":
        ids = [c.case_id for c in self.cases]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Duplicate case_id(s) in dataset: {sorted(duplicates)}")
        return self
