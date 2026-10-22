"""CLI for {{ cookiecutter.project_name }}.

Each command returns a process exit status: 0 on success, 1 on failure, so
scripts and agents can detect a failed run.
"""

import argparse
import sys
from pathlib import Path

import duckdb

from {{ cookiecutter.project_slug }}.apps.transform import MedallionTransformer

DB_PATH = Path("data/{{ cookiecutter.project_slug }}.duckdb")
SAMPLE_CSV = Path("samples/bronze_sample.csv")


def _print_counts(title: str, transformer: MedallionTransformer) -> None:
    status = transformer.get_status()
    print(title)
    print(f"  Bronze: {status.bronze_count:,}")
    print(f"  Silver: {status.silver_count:,}")
    print(f"  Gold:   {status.gold_count:,}")


def load(argv: list[str] | None = None) -> int:
    """Load a CSV file into the bronze table, replacing its contents.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        0 if the file was loaded, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        prog="{{ cookiecutter.project_slug }}-load",
        description=(
            "Load a CSV file (with a header row) into "
            "bronze.{{ cookiecutter.bronze_table }}, replacing its contents. "
            "The pipeline needs id and source_category columns."
        ),
    )
    parser.add_argument("csv", type=Path, help=f"CSV file to load, e.g. {SAMPLE_CSV}")
    args = parser.parse_args(argv)

    if not args.csv.is_file():
        print(f"CSV file not found: {args.csv}", file=sys.stderr)
        return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with MedallionTransformer(DB_PATH) as transformer:
            rows = transformer.load_bronze_csv(args.csv)
    except duckdb.Error as e:
        print(f"Load failed: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {rows:,} rows into bronze.{{ cookiecutter.bronze_table }} ({DB_PATH})")
    return 0


def transform() -> int:
    """Run medallion transformation pipeline.

    Returns:
        0 if every layer succeeded, 1 otherwise.
    """
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        print(
            "Load bronze data first, e.g. "
            f"uv run {{ cookiecutter.project_slug }}-load {SAMPLE_CSV}",
            file=sys.stderr,
        )
        return 1

    try:
        with MedallionTransformer(DB_PATH) as transformer:
            _print_counts("Current state:", transformer)
            print()

            print("Running transformation pipeline...")
            results = transformer.run_full_pipeline()

            for result in results:
                status_icon = "✓" if result.success else "✗"
                print(
                    f"  {status_icon} {result.layer}: "
                    f"{result.rows_source:,} → {result.rows_created:,} "
                    f"({result.duration_seconds:.2f}s)"
                )
                if result.error:
                    print(f"    Error: {result.error}", file=sys.stderr)

            print()
            _print_counts("Final state:", transformer)
    except duckdb.Error as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        return 1

    return 0 if all(result.success for result in results) else 1


if __name__ == "__main__":
    sys.exit(transform())
