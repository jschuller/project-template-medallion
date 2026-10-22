"""Medallion Architecture Transformer for {{ cookiecutter.project_name }}.

Bronze → Silver → Gold pipeline with quality gates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from {{ cookiecutter.project_slug }}.storage.classification import (
    CATEGORY_CASE_SQL,
    QUALITY_CASE_SQL,
    RISK_CASE_SQL,
    SOURCE_CATEGORY_COLUMN,
)

# Columns silver_to_gold adds to every silver column. Silver must not already
# have them: DuckDB would keep both and rename ours (category_1, ...).
GOLD_ADDED_COLUMNS = ("category", "quality_level", "risk_level", "promoted_at")

if TYPE_CHECKING:
{%- if cookiecutter.python_version.split(".")[1] | int >= 11 %}
    from typing import Self
{%- else %}
    # Annotation-only import (see `from __future__ import annotations`), so
    # Python 3.10 needs no runtime typing_extensions dependency.
    from typing_extensions import Self
{%- endif %}


@dataclass
class TransformResult:
    """Result of a layer transformation."""

    layer: str
    table: str
    rows_created: int  # rows written by this run (the table is rebuilt each run)
    rows_source: int
    duration_seconds: float
    success: bool
    error: str | None = None


@dataclass
class MedallionStatus:
    """Current state of medallion layers."""

    bronze_count: int
    silver_count: int
    gold_count: int
    bronze_table: str = "{{ cookiecutter.bronze_table }}"
    silver_table: str = "{{ cookiecutter.silver_table }}"
    gold_table: str = "{{ cookiecutter.gold_table }}"


class MedallionTransformer:
    """Transform data through Bronze → Silver → Gold layers.

    Quality Gates:
    - Bronze → Silver: Validation (e.g., duplicate removal, schema conformance)
    - Silver → Gold: Enrichment (e.g., classification, risk assessment)
    """

    def __init__(self, db_path: Path, read_only: bool = False) -> None:
        """Initialize transformer.

        Args:
            db_path: Path to DuckDB database.
            read_only: If True, open in read-only mode.
        """
        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path), read_only=read_only)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.conn.close()

    def create_schemas(self) -> None:
        """Create medallion schemas if they don't exist.

        Raises:
            duckdb.Error: If a schema cannot be created (for example, the
                database is read-only). The pipeline cannot run without them.
        """
        for schema in ["bronze", "silver", "gold"]:
            self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    def load_bronze_csv(self, csv_path: Path) -> int:
        """Replace the bronze table with the rows of a CSV file.

        Column names come from the header row and types are detected by
        DuckDB. The path is passed as a query parameter, not spliced into SQL.

        Args:
            csv_path: CSV file with a header row.

        Returns:
            Number of rows loaded.

        Raises:
            duckdb.Error: If the file cannot be read or parsed.
        """
        self.create_schemas()
        row = self.conn.execute(
            """
            CREATE OR REPLACE TABLE bronze.{{ cookiecutter.bronze_table }} AS
            SELECT * FROM read_csv(?, header = true)
            """,
            [str(csv_path)],
        ).fetchone()
        return row[0] if row else 0

    def get_status(self) -> MedallionStatus:
        """Get current record counts for each layer.

        Returns:
            MedallionStatus with layer counts.
        """
        bronze = self._safe_count("bronze", "{{ cookiecutter.bronze_table }}")
        silver = self._safe_count("silver", "{{ cookiecutter.silver_table }}")
        gold = self._safe_count("gold", "{{ cookiecutter.gold_table }}")
        return MedallionStatus(
            bronze_count=bronze,
            silver_count=silver,
            gold_count=gold,
        )

    def _safe_count(self, schema: str, table: str) -> int:
        """Count rows in a table, treating a missing table as empty.

        Args:
            schema: Schema name.
            table: Table name.

        Returns:
            Row count, or 0 if the schema or table doesn't exist.

        Raises:
            duckdb.Error: Any other database error (I/O, permissions, a
                corrupt file). These are not reported as zero rows.
        """
        try:
            result = self.conn.execute(
                f"SELECT COUNT(*) FROM {schema}.{table}"
            ).fetchone()
        except duckdb.CatalogException:
            return 0
        return result[0] if result else 0

    def bronze_to_silver(self) -> TransformResult:
        """Transform Bronze → Silver with validation.

        Rebuilds the silver table from bronze on every run (idempotent).
        Override this method with your domain-specific validation logic.

        Returns:
            TransformResult with operation details.
        """
        start = time.time()
        try:
            # Example: deduplicate and validate
            # Customize this SQL for your domain
            # CREATE OR REPLACE rebuilds the table on every run, so re-runs
            # pick up new bronze rows; the statement returns the rows written.
            row = self.conn.execute("""
                CREATE OR REPLACE TABLE silver.{{ cookiecutter.silver_table }} AS
                SELECT DISTINCT * FROM bronze.{{ cookiecutter.bronze_table }}
                WHERE id IS NOT NULL
            """).fetchone()

            source_count = self._safe_count("bronze", "{{ cookiecutter.bronze_table }}")
            dest_count = row[0] if row else 0

            return TransformResult(
                layer="bronze_to_silver",
                table="silver.{{ cookiecutter.silver_table }}",
                rows_created=dest_count,
                rows_source=source_count,
                duration_seconds=time.time() - start,
                success=True,
            )
        except duckdb.Error as e:
            return TransformResult(
                layer="bronze_to_silver",
                table="silver.{{ cookiecutter.silver_table }}",
                rows_created=0,
                rows_source=0,
                duration_seconds=time.time() - start,
                success=False,
                error=str(e),
            )

    def silver_to_gold(self) -> TransformResult:
        """Transform Silver → Gold with enrichment.

        Rebuilds the gold table from silver on every run (idempotent), adding
        the GOLD_ADDED_COLUMNS: category, quality_level and risk_level from the
        CASE SQL generated from storage/classification.py, and promoted_at.
        Silver needs a source_category column and must not already have a
        column with one of those names; the layer fails with an error naming
        it rather than renaming either. Rename the bronze column, or change
        the output names here and in GOLD_ADDED_COLUMNS.
        Override this method with your domain-specific enrichment logic.

        Returns:
            TransformResult with operation details.
        """
        start = time.time()
        try:
            schema_error = self._gold_schema_error()
            if schema_error:
                return TransformResult(
                    layer="silver_to_gold",
                    table="gold.{{ cookiecutter.gold_table }}",
                    rows_created=0,
                    rows_source=0,
                    duration_seconds=time.time() - start,
                    success=False,
                    error=schema_error,
                )

            # Example: enrich with classification from the Python mapping
            # Customize this SQL for your domain
            row = self.conn.execute(f"""
                CREATE OR REPLACE TABLE gold.{{ cookiecutter.gold_table }} AS
                SELECT
                    *,
                    {CATEGORY_CASE_SQL} AS category,
                    {QUALITY_CASE_SQL} AS quality_level,
                    {RISK_CASE_SQL} AS risk_level,
                    CURRENT_TIMESTAMP AS promoted_at
                FROM silver.{{ cookiecutter.silver_table }}
            """).fetchone()

            source_count = self._safe_count("silver", "{{ cookiecutter.silver_table }}")
            dest_count = row[0] if row else 0

            return TransformResult(
                layer="silver_to_gold",
                table="gold.{{ cookiecutter.gold_table }}",
                rows_created=dest_count,
                rows_source=source_count,
                duration_seconds=time.time() - start,
                success=True,
            )
        except duckdb.Error as e:
            return TransformResult(
                layer="silver_to_gold",
                table="gold.{{ cookiecutter.gold_table }}",
                rows_created=0,
                rows_source=0,
                duration_seconds=time.time() - start,
                success=False,
                error=str(e),
            )

    def _gold_schema_error(self) -> str | None:
        """Check that silver has what silver_to_gold reads and none it adds.

        Returns:
            An error message, or None if the silver columns fit.
        """
        rows = self.conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'silver' AND table_name = ?",
            ["{{ cookiecutter.silver_table }}"],
        ).fetchall()
        columns = {name.lower() for (name,) in rows}
        if not columns:
            return "silver.{{ cookiecutter.silver_table }} does not exist"
        if SOURCE_CATEGORY_COLUMN not in columns:
            return (
                "silver.{{ cookiecutter.silver_table }} has no "
                f"{SOURCE_CATEGORY_COLUMN} column to classify"
            )
        clashes = [name for name in GOLD_ADDED_COLUMNS if name in columns]
        if clashes:
            return (
                "silver.{{ cookiecutter.silver_table }} already has column(s) "
                f"{', '.join(clashes)}, which gold adds; rename them in bronze"
            )
        return None

    def run_full_pipeline(self) -> list[TransformResult]:
        """Run complete Bronze → Silver → Gold pipeline.

        Returns:
            List of TransformResults for each layer that ran. Silver → Gold
            is skipped if Bronze → Silver failed, so the pipeline succeeded
            only if every result has ``success=True``.

        Raises:
            duckdb.Error: If the medallion schemas cannot be created.
        """
        results = []

        # Ensure schemas exist (raises if they cannot be created)
        self.create_schemas()

        # Bronze → Silver
        results.append(self.bronze_to_silver())

        # Silver → Gold (only if silver succeeded)
        if results[-1].success:
            results.append(self.silver_to_gold())

        return results
