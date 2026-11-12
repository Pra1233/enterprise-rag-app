"""Loaders for evaluation datasets. Supports JSON (native, preferred — lists
and nested metadata map directly) and CSV (flattened: list fields are
pipe-separated, metadata is a JSON object string — see datasets/README.md).

Adding evaluation questions means editing/adding a dataset file here; it never
requires touching application code (src/ingestion, src/retrieval, src/api).
"""

import csv
import json
from pathlib import Path

from pydantic import ValidationError

from src.evaluation.dataset import EvaluationCase, EvaluationDataset


class DatasetLoadError(Exception):
    """Raised when a dataset file is missing, malformed, or fails validation."""


def load_dataset(path: str | Path) -> EvaluationDataset:
    """Load an evaluation dataset from .json or .csv, dispatching on extension."""
    file_path = Path(path)
    if not file_path.exists():
        raise DatasetLoadError(f"Dataset file not found: {file_path}")

    if file_path.suffix.lower() == ".json":
        return load_from_json(file_path)
    if file_path.suffix.lower() == ".csv":
        return load_from_csv(file_path)
    raise DatasetLoadError(f"Unsupported dataset file extension '{file_path.suffix}' (expected .json or .csv)")


def load_from_json(path: str | Path) -> EvaluationDataset:
    file_path = Path(path)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetLoadError(f"Invalid JSON in {file_path}: {exc}") from exc

    try:
        return EvaluationDataset.model_validate(raw)
    except ValidationError as exc:
        raise DatasetLoadError(f"Dataset validation failed for {file_path}:\n{exc}") from exc


_LIST_FIELDS = ("ground_truth_contexts", "expected_document_ids", "expected_chunk_ids", "expected_source_references")
_LIST_SEPARATOR = "|"


def _split_list_field(value: str) -> list[str]:
    return [v.strip() for v in value.split(_LIST_SEPARATOR) if v.strip()] if value else []


def load_from_csv(path: str | Path) -> EvaluationDataset:
    """Load from CSV. Expected columns: question, ground_truth, and optionally
    ground_truth_contexts, expected_document_ids, expected_chunk_ids,
    expected_source_references (pipe-separated, e.g. "doc-001|doc-002"),
    metadata (a JSON object string, e.g. '{"document_type": "financial_report"}'),
    expects_refusal ("true"/"false"), case_id.
    """
    file_path = Path(path)
    cases: list[dict] = []

    try:
        with file_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_number, row in enumerate(reader, start=2):  # header is row 1
                case: dict = {"question": row.get("question", ""), "ground_truth": row.get("ground_truth", "")}

                for field in _LIST_FIELDS:
                    if row.get(field):
                        case[field] = _split_list_field(row[field])

                if row.get("metadata"):
                    try:
                        case["metadata"] = json.loads(row["metadata"])
                    except json.JSONDecodeError as exc:
                        raise DatasetLoadError(
                            f"{file_path} row {row_number}: `metadata` column is not valid JSON: {exc}"
                        ) from exc

                if row.get("expects_refusal"):
                    case["expects_refusal"] = row["expects_refusal"].strip().lower() in ("true", "1", "yes")

                if row.get("case_id"):
                    case["case_id"] = row["case_id"]

                cases.append(case)
    except OSError as exc:
        raise DatasetLoadError(f"Could not read {file_path}: {exc}") from exc

    try:
        validated_cases = [EvaluationCase.model_validate(c) for c in cases]
        return EvaluationDataset(
            name=file_path.stem, description=f"Loaded from {file_path.name}", cases=validated_cases
        )
    except ValidationError as exc:
        raise DatasetLoadError(f"Dataset validation failed for {file_path}:\n{exc}") from exc
