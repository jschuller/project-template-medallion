---
description: Run medallion transformation pipeline
---

# Transform Command

Runs the Bronze → Silver → Gold transformation pipeline.

Bronze must be loaded first. For the bundled sample:

```bash
uv run {{ cookiecutter.project_slug }}-load samples/bronze_sample.csv
```

## Usage

```
/transform
```

## What It Does

1. Shows current layer counts (bronze/silver/gold)
2. Runs bronze_to_silver transformation with validation
3. Runs silver_to_gold transformation with enrichment
4. Reports final counts and promotion rates

## Example Output

After loading the bundled sample (silver drops one duplicate and one row
without an id; gold is a 1:1 rebuild of silver with classification added):

```
Current state:
  Bronze: 7
  Silver: 0
  Gold:   0

Running transformation pipeline...
  ✓ bronze_to_silver: 7 → 5 (0.00s)
  ✓ silver_to_gold: 5 → 5 (0.00s)

Final state:
  Bronze: 7
  Silver: 5
  Gold:   5
```

The command exits with status 1 if the database is missing or a layer fails.

## Implementation

```bash
uv run {{ cookiecutter.project_slug }}-transform
```
