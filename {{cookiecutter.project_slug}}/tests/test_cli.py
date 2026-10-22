"""Tests for the {{ cookiecutter.project_name }} CLI exit status."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from {{ cookiecutter.project_slug }} import cli


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test from an empty project directory with a data/ folder."""
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _create_db(bronze_ddl: str | None) -> None:
    conn = duckdb.connect(str(cli.DB_PATH))
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        if bronze_ddl:
            conn.execute(bronze_ddl)
    finally:
        conn.close()


def test_transform_exits_1_without_database(project_dir: Path) -> None:
    assert cli.transform() == 1


def test_transform_exits_1_when_a_layer_fails(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_db(bronze_ddl=None)  # database exists, bronze table does not

    assert cli.transform() == 1
    assert "{{ cookiecutter.bronze_table }}" in capsys.readouterr().err


def test_transform_exits_0_on_success(project_dir: Path) -> None:
    _create_db(
        "CREATE TABLE bronze.{{ cookiecutter.bronze_table }} AS "
        "SELECT * FROM (VALUES (1, 'a', 'type_a'), (2, 'b', NULL)) t(id, name, source_category)"
    )

    assert cli.transform() == 0
