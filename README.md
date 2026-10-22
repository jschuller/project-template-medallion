# Medallion Architecture Template

Cookiecutter template for creating data lakehouse projects with Bronze → Silver → Gold architecture.

## Quick Start

```bash
# Install cookiecutter
pip install cookiecutter

# Generate project from template
cookiecutter gh:jschuller/project-template-medallion

# Run the pipeline on the bundled sample data
cd your_project
uv run your_project-load samples/bronze_sample.csv
uv run your_project-transform
```

## What You Get

```
your_project/
├── src/your_project/
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
├── samples/                  # Sample bronze CSV for the quickstart
├── tests/                    # pytest suite
├── .gitignore                # Keeps *.duckdb and data/ out of git
├── pyproject.toml
└── README.md
```

## Features

- **DuckDB-based** medallion architecture (Bronze → Silver → Gold)
- **Claude Code integration** with CLAUDE.md and transform skill
- **Classification registry pattern** for domain mapping
- **Type-safe Python** with quality gates at each layer
- **Configurable table names** via cookiecutter variables

## Customization

1. Edit `storage/classification.py` with your domain mappings
2. Define quality gates in `apps/transform.py`
3. Add domain-specific enums in `storage/models.py`

## Configuration

When running cookiecutter, you can customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | My Medallion Project | Display name |
| `project_slug` | my_medallion_project | Python package name |
| `bronze_table` | raw_data | Bronze layer table name |
| `silver_table` | verified_data | Silver layer table name |
| `gold_table` | assets | Gold layer table name |

## Upgrading Projects Generated Before October 2026

The October 2026 template changes break code and data that relied on the old
behaviour:

- **Gold has no `status` column any more.** It held the literal
  `'CLASSIFIED'`. Gold now adds `category`, `quality_level`, `risk_level` and
  `promoted_at`, so bronze must not have columns with those names.
- **Bronze needs a `source_category` column** (and `id`, as before); gold fails
  without it. The new `<project_slug>-load` command refuses a CSV that lacks
  either.
- **The transform command exits 1 on failure** (missing database, a failed
  layer, a DuckDB error) instead of always 0.
- **A missing-table count is still 0, but other database errors now raise**
  instead of reading as 0 rows. `create_schemas()` returns nothing and raises
  on failure.
- **Generated projects ship a `.gitignore`** that ignores `*.duckdb` and the
  contents of `data/`. Copy it in, and `git rm --cached` any database you
  committed.

## Documentation

See [docs/MEDALLION-PATTERN.md](docs/MEDALLION-PATTERN.md) for the complete pattern guide.

## License

MIT
