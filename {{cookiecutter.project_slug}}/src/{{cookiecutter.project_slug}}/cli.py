"""CLI for {{ cookiecutter.project_name }}.

Each command returns a process exit status: 0 on success, 1 on failure, so
scripts and agents can detect a failed run.
"""

import sys
from pathlib import Path

import duckdb

from {{ cookiecutter.project_slug }}.apps.transform import MedallionTransformer

DB_PATH = Path("data/{{ cookiecutter.project_slug }}.duckdb")


def _print_counts(title: str, transformer: MedallionTransformer) -> None:
    status = transformer.get_status()
    print(title)
    print(f"  Bronze: {status.bronze_count:,}")
    print(f"  Silver: {status.silver_count:,}")
    print(f"  Gold:   {status.gold_count:,}")


def transform() -> int:
    """Run medallion transformation pipeline.

    Returns:
        0 if every layer succeeded, 1 otherwise.
    """
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}", file=sys.stderr)
        print("Create bronze layer data first.", file=sys.stderr)
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
