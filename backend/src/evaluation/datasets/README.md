# Evaluation datasets

## `sample_dataset.json`

11 illustrative questions (10 answerable + 1 refusal case) in the shape
`evaluation.dataset.EvaluationDataset` expects. **The document IDs
(`document-001` etc.) are placeholders.** Retrieval metrics against this file
will legitimately score near zero unless you've ingested documents whose
`document_id`s and content actually match — that's correct behavior, not a
bug. This file demonstrates dataset *structure*, not a real evaluation
result; never report a run against it as "real" evaluation numbers unless
the referenced documents genuinely exist in the target tenant.

To build a real evaluation set: ingest your documents via `POST
/api/v1/ingestion/upload`, note the `document_id`s returned, and write a new
dataset file referencing them.

## Schema

Each case (`EvaluationCase` in `dataset.py`):

| Field | Required | Notes |
|---|---|---|
| `question` | yes | |
| `ground_truth` | yes | The reference answer. For `expects_refusal: true` cases, describe *why* it's unanswerable — never a guessed fact. |
| `ground_truth_contexts` | no | Text passages the LLM should have been grounded in. Used for RAGAS context metrics. |
| `expected_document_ids` | no | Drives **document-level** retrieval metrics (Recall@K, Precision@K, MRR, NDCG@K). |
| `expected_chunk_ids` | no | Only set this if you have real chunk-level ground truth — it drives separate **chunk-level** metrics and is never conflated with document-level ones. |
| `expected_source_references` | no | Human-readable citations (e.g. `"Annual Report FY2025, p.3"`) — informational only, not used in scoring. |
| `metadata` | no | e.g. `{"document_type": "financial_report"}`, passed through as a retrieval filter. |
| `expects_refusal` | no, default `false` | When `true`, the only correct system behavior is refusing to answer (`is_relevant == False` from the LangGraph workflow) — RAGAS faithfulness/relevancy are skipped for these cases since there's no real answer to score against. |

## CSV format

Loaded via `dataset_loader.load_from_csv`. List-valued fields
(`ground_truth_contexts`, `expected_document_ids`, `expected_chunk_ids`,
`expected_source_references`) are pipe-separated (`doc-001|doc-002`);
`metadata` is a JSON object string (`{"document_type": "financial_report"}`);
`expects_refusal` is `true`/`false`.

## Adding questions

Add a new JSON (or CSV) file in this directory, or append cases to an
existing one. No application code needs to change — `EvaluationDataset` /
`load_dataset()` validate the file at load time and reject anything
malformed before it ever reaches the evaluator.
