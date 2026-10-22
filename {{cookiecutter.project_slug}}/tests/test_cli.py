"""Tests for the {{ cookiecutter.project_name }} CLI exit status."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from {{ cookiecutter.project_slug }} import cli
from {{ cookiecutter.project_slug }}.apps.transform import MedallionTransformer

SAMPLE_CSV = Path(__file__).resolve().parents[1] / cli.SAMPLE_CSV


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


def test_quickstart_sample_runs_end_to_end(project_dir: Path) -> None:
    # The README quickstart: load the bundled sample, then transform.
    assert cli.load([str(SAMPLE_CSV)]) == 0
    assert cli.transform() == 0

    with MedallionTransformer(cli.DB_PATH, read_only=True) as transformer:
        status = transformer.get_status()
    # 7 rows; silver drops one duplicate and one row without an id.
    assert (status.bronze_count, status.silver_count, status.gold_count) == (7, 5, 5)


def test_load_replaces_bronze(project_dir: Path) -> None:
    assert cli.load([str(SAMPLE_CSV)]) == 0
    assert cli.load([str(SAMPLE_CSV)]) == 0

    with MedallionTransformer(cli.DB_PATH, read_only=True) as transformer:
        assert transformer.get_status().bronze_count == 7


def test_load_exits_1_for_missing_file(project_dir: Path) -> None:
    assert cli.load(["no-such-file.csv"]) == 1
    assert not cli.DB_PATH.exists()


def test_load_exits_1_for_unreadable_csv(project_dir: Path) -> None:
    bad = project_dir / "bad.csv"
    bad.write_bytes(b"id,name\n1,\xff\xfe\n")  # not valid UTF-8

    assert cli.load([str(bad)]) == 1
