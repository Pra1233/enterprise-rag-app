import json

import pytest
from pydantic import ValidationError

from src.evaluation.dataset import EvaluationCase, EvaluationDataset
from src.evaluation.dataset_loader import DatasetLoadError, load_dataset, load_from_csv, load_from_json
from src.evaluation.metrics import (
    dedupe_preserve_order,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

# --- 1. Dataset loading ---


def test_load_sample_dataset_json():
    dataset = load_dataset("src/evaluation/datasets/sample_dataset.json")
    assert dataset.name == "sample_dataset"
    assert len(dataset.cases) >= 10
    assert any(c.expects_refusal for c in dataset.cases)


def test_load_from_json_dispatches_correctly(tmp_path):
    path = tmp_path / "ds.json"
    path.write_text(json.dumps({"name": "tiny", "cases": [{"question": "Q?", "ground_truth": "A."}]}), encoding="utf-8")
    dataset = load_dataset(path)
    assert dataset.name == "tiny"
    assert len(dataset.cases) == 1


def test_load_from_csv():
    import csv

    path_str = "/tmp/test_eval_dataset.csv"
    with open(path_str, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["question", "ground_truth", "expected_document_ids", "metadata", "expects_refusal"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "question": "What is X?",
                "ground_truth": "X is Y.",
                "expected_document_ids": "doc-1|doc-2",
                "metadata": '{"document_type": "faq"}',
                "expects_refusal": "false",
            }
        )

    dataset = load_from_csv(path_str)
    case = dataset.cases[0]
    assert case.expected_document_ids == ["doc-1", "doc-2"]
    assert case.metadata == {"document_type": "faq"}
    assert case.expects_refusal is False


def test_missing_dataset_file_raises():
    with pytest.raises(DatasetLoadError):
        load_dataset("does/not/exist.json")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "ds.yaml"
    path.write_text("not supported", encoding="utf-8")
    with pytest.raises(DatasetLoadError):
        load_dataset(path)


# --- 2. Dataset validation ---


def test_evaluation_case_requires_question_and_ground_truth():
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({"question": "", "ground_truth": "A."})


def test_evaluation_case_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate({"question": "Q?", "ground_truth": "A.", "not_a_real_field": 1})


def test_evaluation_dataset_requires_at_least_one_case():
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate({"name": "empty", "cases": []})


def test_evaluation_dataset_rejects_duplicate_case_ids():
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(
            {
                "name": "dupes",
                "cases": [
                    {"case_id": "a", "question": "Q1?", "ground_truth": "A1."},
                    {"case_id": "a", "question": "Q2?", "ground_truth": "A2."},
                ],
            }
        )


def test_invalid_json_dataset_raises_dataset_load_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(DatasetLoadError):
        load_from_json(path)


# --- 3/4/5/6. Retrieval metrics: Recall@K, Precision@K, MRR, NDCG, Hit Rate@K ---


RETRIEVED = ["d2", "d5", "d1", "d3"]
RELEVANT = {"d1", "d3", "d9"}


def test_recall_at_k():
    assert recall_at_k(RETRIEVED, RELEVANT, 3) == pytest.approx(1 / 3)
    assert recall_at_k(RETRIEVED, RELEVANT, 4) == pytest.approx(2 / 3)


def test_recall_at_k_returns_none_without_ground_truth():
    assert recall_at_k(RETRIEVED, set(), 3) is None


def test_precision_at_k():
    assert precision_at_k(RETRIEVED, RELEVANT, 3) == pytest.approx(1 / 3)
    assert precision_at_k([], RELEVANT, 3) == 0.0


def test_mean_reciprocal_rank():
    assert mean_reciprocal_rank(RETRIEVED, RELEVANT) == pytest.approx(1 / 3)  # first hit (d1) at rank 3
    assert mean_reciprocal_rank(["x", "y"], RELEVANT) == 0.0
    assert mean_reciprocal_rank(RETRIEVED, set()) is None


def test_hit_rate_at_k():
    assert hit_rate_at_k(RETRIEVED, RELEVANT, 2) == 0.0  # d2, d5 — neither relevant
    assert hit_rate_at_k(RETRIEVED, RELEVANT, 3) == 1.0  # d1 enters at rank 3


def test_ndcg_at_k_perfect_ranking_is_one():
    retrieved = ["d1", "d3"]
    relevant = {"d1", "d3"}
    assert ndcg_at_k(retrieved, relevant, 2) == pytest.approx(1.0)


def test_ndcg_at_k_matches_hand_computed_value():
    # DCG = 0/log2(2) + 0/log2(3) + 1/log2(4) + 1/log2(5); IDCG uses 3 ideal hits (min(|relevant|, k)).
    import math

    dcg = 1 / math.log2(4) + 1 / math.log2(5)
    idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(RETRIEVED, RELEVANT, 4) == pytest.approx(dcg / idcg)


def test_dedupe_preserve_order():
    assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
