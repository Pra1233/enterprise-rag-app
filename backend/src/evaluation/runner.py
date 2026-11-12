"""Command-line evaluation runner.

Example:
    python -m src.evaluation.runner \\
        --dataset src/evaluation/datasets/sample_dataset.json \\
        --top-k 5 --mode full --tenant-id eval-tenant

Compare against a previous run's baseline:
    python -m src.evaluation.runner --dataset ... --baseline evaluation_results/run1/summary.json
"""

import argparse
import asyncio
import logging
import sys

from src.evaluation.dataset_loader import DatasetLoadError, load_dataset
from src.evaluation.evaluator import run_evaluation
from src.evaluation.reports import generate_all_reports
from src.evaluation.retrieval_eval import RETRIEVAL_STRATEGIES

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RAG evaluation (retrieval and/or answer quality).")
    parser.add_argument("--dataset", required=True, help="Path to a .json or .csv evaluation dataset.")
    parser.add_argument("--tenant-id", default="eval-tenant", help="Tenant whose indexed documents to query.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--mode",
        choices=["retrieval", "answer", "full"],
        default="full",
        help="retrieval = retrieval metrics only; answer = run the full RAG workflow and score answers; full = both.",
    )
    parser.add_argument(
        "--strategies",
        default=",".join(RETRIEVAL_STRATEGIES),
        help=f"Comma-separated subset of: {','.join(RETRIEVAL_STRATEGIES)}",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Max cases evaluated concurrently — bounds Groq rate-limit exposure and local resource usage.",
    )
    parser.add_argument("--output-dir", default="evaluation_results", help="Directory to write reports/charts into.")
    parser.add_argument(
        "--baseline", default=None, help="Path to a previous run's summary.json to compare this run against."
    )
    return parser


async def main_async(args: argparse.Namespace) -> int:
    try:
        dataset = load_dataset(args.dataset)
    except DatasetLoadError as exc:
        logger.error("%s", exc)
        return 1

    strategies = tuple(s.strip() for s in args.strategies.split(",") if s.strip())
    unknown = set(strategies) - set(RETRIEVAL_STRATEGIES)
    if unknown:
        logger.error("Unknown retrieval strategy(ies): %s (expected one of %s)", sorted(unknown), RETRIEVAL_STRATEGIES)
        return 1

    logger.info(
        "Running evaluation: dataset=%s cases=%d mode=%s top_k=%d strategies=%s max_concurrency=%d",
        dataset.name,
        len(dataset.cases),
        args.mode,
        args.top_k,
        strategies,
        args.max_concurrency,
    )

    run = await run_evaluation(
        dataset=dataset,
        tenant_id=args.tenant_id,
        mode=args.mode,
        top_k=args.top_k,
        strategies=strategies,
        max_concurrency=args.max_concurrency,
    )

    paths = generate_all_reports(run, output_dir=args.output_dir, baseline_path=args.baseline)

    logger.info(
        "Evaluation complete: %d/%d cases succeeded (%d failed: %s)",
        dataset.cases.__len__() - len(run.failed_case_ids),
        len(dataset.cases),
        len(run.failed_case_ids),
        run.failed_case_ids,
    )
    for label, path in paths.items():
        logger.info("  %s -> %s", label, path)

    # Non-zero exit only when EVERY case failed — a partial failure is
    # reported (see failed_case_ids in the summary) but isn't a hard CI failure
    # on its own, since transient Groq/network blips shouldn't fail a build.
    return 1 if run.failed_case_ids and len(run.failed_case_ids) == len(dataset.cases) else 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    args = build_arg_parser().parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
