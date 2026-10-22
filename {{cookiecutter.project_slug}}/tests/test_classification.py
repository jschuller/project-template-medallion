"""Tests for the classification CASE SQL generator."""

from __future__ import annotations

import duckdb
import pytest

from {{ cookiecutter.project_slug }}.storage.classification import (
    ClassificationInfo,
    generate_case_sql,
    sql_identifier,
    sql_string_literal,
)


def _info(category: str) -> ClassificationInfo:
    return ClassificationInfo(
        category=category, quality_level="q", risk_level="r", description="d"
    )


def _evaluate(case_sql: str, column: str, inputs: list[str | None]) -> list[str]:
    """Evaluate a CASE expression in DuckDB against one row per input."""
    conn = duckdb.connect()
    try:
        conn.execute(f"CREATE TABLE t ({sql_identifier(column)} VARCHAR, n INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?, ?)", [(v, i) for i, v in enumerate(inputs)])
        rows = conn.execute(f"SELECT {case_sql} FROM t ORDER BY n").fetchall()
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone() == (len(inputs),)
    finally:
        conn.close()
    return [row[0] for row in rows]


def test_single_quotes_in_keys_values_and_default_are_escaped() -> None:
    mapping = {"o'neil": _info("it's"), "plain": _info("PLAIN")}
    sql = generate_case_sql(mapping, "source_category", "category", "n'a")

    assert _evaluate(sql, "source_category", ["o'neil", "plain", "other"]) == [
        "it's",
        "PLAIN",
        "n'a",
    ]


def test_injection_attempt_is_returned_as_data() -> None:
    payload = "x' END; DROP TABLE t; --"
    sql = generate_case_sql({payload: _info(payload)}, "source_category", "category", "-")

    # _evaluate also checks that table t still holds every row afterwards.
    assert _evaluate(sql, "source_category", [payload]) == [payload]


def test_backslashes_are_literal() -> None:
    sql = generate_case_sql({"a\\b": _info("c\\d")}, "source_category", "category", "-")

    assert _evaluate(sql, "source_category", ["a\\b"]) == ["c\\d"]


def test_column_name_is_quoted() -> None:
    column = 'odd "col"'
    sql = generate_case_sql({"k": _info("V")}, column, "category", "-")

    assert _evaluate(sql, column, ["k", "z"]) == ["V", "-"]


def test_empty_mapping_returns_the_default() -> None:
    sql = generate_case_sql({}, "source_category", "category", "UNKNOWN")

    assert _evaluate(sql, "source_category", ["anything"]) == ["UNKNOWN"]


def test_unknown_output_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown ClassificationInfo field"):
        generate_case_sql({"k": _info("V")}, "source_category", "__class__", "-")


def test_literal_helpers_reject_nul() -> None:
    assert sql_string_literal("it's") == "'it''s'"
    with pytest.raises(ValueError):
        sql_string_literal("a\x00b")
    with pytest.raises(ValueError):
        sql_identifier("")
