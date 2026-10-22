"""Tests for the {{ cookiecutter.project_name }} medallion pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from {{ cookiecutter.project_slug }}.apps.transform import MedallionTransformer
from {{ cookiecutter.project_slug }}.storage.classification import (
    get_classification_info,
)

BRONZE = "bronze.{{ cookiecutter.bronze_table }}"
GOLD = "gold.{{ cookiecutter.gold_table }}"


def _insert_bronze(
    transformer: MedallionTransformer,
    rows: list[tuple[int | None, str, str | None]],
) -> None:
    transformer.conn.executemany(f"INSERT INTO {BRONZE} VALUES (?, ?, ?)", rows)


@pytest.fixture
def transformer(tmp_path: Path) -> Iterator[MedallionTransformer]:
    """Transformer on a temporary database with a seeded bronze table."""
    with MedallionTransformer(tmp_path / "test.duckdb") as transformer:
        transformer.create_schemas()
        transformer.conn.execute(
            f"CREATE TABLE {BRONZE} (id INTEGER, name VARCHAR, source_category VARCHAR)"
        )
        # One exact duplicate and one row without an id: silver drops both.
        _insert_bronze(
            transformer,
            [(1, "a", "type_a"), (2, "b", "TYPE_B"), (2, "b", "TYPE_B"), (None, "no id", "type_c")],
        )
        yield transformer


def test_pipeline_deduplicates_and_drops_null_ids(
    transformer: MedallionTransformer,
) -> None:
    results = transformer.run_full_pipeline()

    assert [r.success for r in results] == [True, True]
    assert [(r.rows_source, r.rows_created) for r in results] == [(4, 2), (2, 2)]
    status = transformer.get_status()
    assert (status.bronze_count, status.silver_count, status.gold_count) == (4, 2, 2)


def test_rerun_promotes_new_bronze_rows(transformer: MedallionTransformer) -> None:
    transformer.run_full_pipeline()
    _insert_bronze(
        transformer, [(3, "c", None), (3, "c", None), (None, "still no id", None)]
    )

    results = transformer.run_full_pipeline()

    assert [r.success for r in results] == [True, True]
    assert [(r.rows_source, r.rows_created) for r in results] == [(7, 3), (3, 3)]
    status = transformer.get_status()
    assert (status.bronze_count, status.silver_count, status.gold_count) == (7, 3, 3)


def test_gold_classification_matches_python(
    transformer: MedallionTransformer,
) -> None:
    _insert_bronze(transformer, [(4, "d", "Type_C"), (5, "e", "not mapped")])
    transformer.run_full_pipeline()

    rows = transformer.conn.execute(
        f"SELECT source_category, category, quality_level, risk_level FROM {GOLD} ORDER BY id"
    ).fetchall()

    assert [r[1] for r in rows] == ["TYPE_A", "TYPE_B", "TYPE_C", "UNKNOWN"]
    for source_category, *classified in rows:
        info = get_classification_info(source_category)
        assert classified == [info.category, info.quality_level, info.risk_level]


def test_missing_bronze_table_fails_the_layer(tmp_path: Path) -> None:
    with MedallionTransformer(tmp_path / "empty.duckdb") as transformer:
        results = transformer.run_full_pipeline()

    # Silver fails with the catalog error; gold is skipped.
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error and "{{ cookiecutter.bronze_table }}" in results[0].error


def test_missing_tables_count_as_zero(tmp_path: Path) -> None:
    with MedallionTransformer(tmp_path / "empty.duckdb") as transformer:
        status = transformer.get_status()

    assert (status.bronze_count, status.silver_count, status.gold_count) == (0, 0, 0)


def test_count_errors_are_not_reported_as_zero(
    transformer: MedallionTransformer,
) -> None:
    # A bronze relation that exists but fails when read: only a missing table
    # may be counted as 0; other database errors must surface.
    transformer.conn.execute(f"DROP TABLE {BRONZE}")
    transformer.conn.execute(
        f"CREATE VIEW {BRONZE} AS SELECT 1 AS id WHERE error('broken source') IS NULL"
    )

    with pytest.raises(duckdb.Error, match="broken source"):
        transformer.get_status()

    results = transformer.run_full_pipeline()
    assert [r.success for r in results] == [False]
    assert results[0].error and "broken source" in results[0].error


def test_schema_creation_failure_aborts_the_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "readonly.duckdb"
    duckdb.connect(str(db_path)).close()

    with (
        MedallionTransformer(db_path, read_only=True) as transformer,
        pytest.raises(duckdb.Error),
    ):
        transformer.run_full_pipeline()


def test_integer_categories_classify(tmp_path: Path) -> None:
    with MedallionTransformer(tmp_path / "codes.duckdb") as transformer:
        transformer.create_schemas()
        transformer.conn.execute(
            f"CREATE TABLE {BRONZE} AS SELECT * FROM (VALUES (1, 1), (2, 2)) t(id, source_category)"
        )
        results = transformer.run_full_pipeline()
        rows = transformer.conn.execute(
            f"SELECT source_category, category FROM {GOLD} ORDER BY id"
        ).fetchall()

    assert [r.success for r in results] == [True, True]
    assert [category for _, category in rows] == [
        get_classification_info(code).category for code, _ in rows
    ]


@pytest.mark.parametrize("column", ["category", "Quality_Level", "risk_level", "promoted_at"])
def test_gold_fails_when_bronze_has_an_output_column(tmp_path: Path, column: str) -> None:
    with MedallionTransformer(tmp_path / "clash.duckdb") as transformer:
        transformer.create_schemas()
        transformer.conn.execute(
            f"CREATE TABLE {BRONZE} AS SELECT 1 AS id, 'type_a' AS source_category, "
            f"'mine' AS {column}"
        )
        results = transformer.run_full_pipeline()

    assert [r.success for r in results] == [True, False]
    assert results[1].error and column.lower() in results[1].error
    assert "rename" in results[1].error


def test_gold_fails_without_source_category(tmp_path: Path) -> None:
    with MedallionTransformer(tmp_path / "nocat.duckdb") as transformer:
        transformer.create_schemas()
        transformer.conn.execute(f"CREATE TABLE {BRONZE} AS SELECT 1 AS id")
        results = transformer.run_full_pipeline()

    assert [r.success for r in results] == [True, False]
    assert results[1].error and "source_category" in results[1].error
