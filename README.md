# Medallion Architecture Template

Cookiecutter template for creating data lakehouse projects with Bronze → Silver → Gold architecture.

## Quick Start

```bash
# Install cookiecutter
pip install cookiecutter

# Generate project from template
cookiecutter gh:jschuller/project-template-medallion
```

## What You Get

```
your_project/
├── src/your_project/
│   ├── apps/
│   │   └── transform.py      # MedallionTransformer
│   └── storage/
│       ├── classification.py # Domain mapping
│       └── models.py         # Domain enums
├── .claude/
│   ├── CLAUDE.md             # Dev instructions
│   └── commands/
│       └── transform.md      # Transform skill
├── data/                     # DuckDB storage
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

## Documentation

See [docs/MEDALLION-PATTERN.md](docs/MEDALLION-PATTERN.md) for the complete pattern guide.

## License

MIT
