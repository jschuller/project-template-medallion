# CLAUDE.md

{{ cookiecutter.project_name }}: Medallion Architecture Data Project

## Setup

```bash
uv sync --all-extras
```

## Commands

```bash
# Load a CSV into bronze (replaces bronze.{{ cookiecutter.bronze_table }}); the sample is for the quickstart
uv run {{ cookiecutter.project_slug }}-load samples/bronze_sample.csv

# Run transformation pipeline
uv run {{ cookiecutter.project_slug }}-transform
```

Both commands exit with status 1 on failure.

## Skills

```
/transform    Run Bronze → Silver → Gold pipeline
```

## Schema

| Layer | Table | Purpose |
|-------|-------|---------|
| Bronze | `{{ cookiecutter.bronze_table }}` | Raw ingested data |
| Silver | `{{ cookiecutter.silver_table }}` | Validated, deduplicated |
| Gold | `{{ cookiecutter.gold_table }}` | Enriched, production-ready |

**Quality Gates:**
- Bronze → Silver: Validation (nulls, duplicates, schema)
- Silver → Gold: Enrichment (classification, risk assessment)

Bronze needs an `id` column (silver drops rows where it is NULL) and a
`source_category` column (text or numeric codes). Gold adds `category`,
`quality_level` and `risk_level` from the CASE SQL generated from
`storage/classification.py`, plus `promoted_at` (`GOLD_ADDED_COLUMNS`); the
match is on the value's text, case-insensitively, like
`get_classification_info()`. If bronze already has a column with one of those
names, gold fails with an error naming it: rename the bronze column.

## Architecture

```
src/{{ cookiecutter.project_slug }}/
├── apps/
│   └── transform.py      # MedallionTransformer
├── storage/
│   ├── classification.py # Domain mapping
│   └── models.py         # Domain enums
└── cli.py                # CLI entry points (load, transform)

data/
└── {{ cookiecutter.project_slug }}.duckdb  # Persistent storage (gitignored; never commit it)
samples/
└── bronze_sample.csv     # Quickstart bronze data
```

## Key Patterns

```python
# Always use context managers
with MedallionTransformer(db_path) as transformer:
    results = transformer.run_full_pipeline()

# Classification from Python dict → SQL CASE (used by silver_to_gold)
from {{ cookiecutter.project_slug }}.storage.classification import CATEGORY_CASE_SQL
```

## Customization

1. Edit `storage/models.py` with your domain enums
2. Edit `storage/classification.py` with your domain mappings
3. Override `bronze_to_silver()` and `silver_to_gold()` in transform.py

## Tests

```bash
pytest tests/ -v
```
