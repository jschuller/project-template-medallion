# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

## Setup

```bash
# Install dependencies
uv sync --all-extras

# Or with pip
pip install -e ".[dev]"
```

## Usage

```bash
# 1. Load the bundled sample CSV into bronze (replaces bronze.{{ cookiecutter.bronze_table }})
uv run {{ cookiecutter.project_slug }}-load samples/bronze_sample.csv

# 2. Run the transformation pipeline
uv run {{ cookiecutter.project_slug }}-transform
```

The sample has 7 rows, including one duplicate and one row without an `id`,
so the pipeline reports `7 → 5` for bronze → silver and `5 → 5` for
silver → gold. Gold adds `category`, `quality_level` and `risk_level` from
`storage/classification.py`.

To load your own data, pass any CSV with a header row. The shipped
transforms need an `id` column and a `source_category` column. Both
commands exit with status 1 on failure.

## Architecture

This project uses the **Medallion Architecture** pattern:

```
Bronze (Raw) → Silver (Validated) → Gold (Enriched)
```

| Layer | Table | Purpose |
|-------|-------|---------|
| Bronze | `{{ cookiecutter.bronze_table }}` | Raw ingested data |
| Silver | `{{ cookiecutter.silver_table }}` | Validated, deduplicated |
| Gold | `{{ cookiecutter.gold_table }}` | Enriched, production-ready |

## Project Structure

```
{{ cookiecutter.project_slug }}/
├── src/{{ cookiecutter.project_slug }}/
│   ├── apps/
│   │   └── transform.py      # MedallionTransformer
│   ├── storage/
│   │   ├── classification.py # Domain mapping
│   │   └── models.py         # Domain enums
│   └── cli.py                # load and transform commands
├── .claude/
│   ├── CLAUDE.md             # Dev instructions
│   └── commands/
│       └── transform.md      # Transform skill
├── data/                     # DuckDB storage (contents gitignored)
├── samples/
│   └── bronze_sample.csv     # Quickstart data for the load command
├── tests/                    # pytest suite
├── .gitignore                # Keeps *.duckdb and data/ out of git
├── pyproject.toml
└── README.md
```

## Customization

1. **Define your domain enums** in `storage/models.py`
2. **Create classification mappings** in `storage/classification.py`
3. **Implement quality gates** by overriding transform methods

## Development

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check src/
```

## License

MIT
