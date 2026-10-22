"""Classification and inference logic for {{ cookiecutter.project_name }}.

Pattern: Define mappings as Python dicts, generate SQL CASE statements.
This ensures a single source of truth for classification logic: the gold
layer (apps/transform.py) uses the generated CASE SQL, and
get_classification_info gives the same answer in Python.

Matching is case-insensitive in both: the input is converted to text,
lower-cased and looked up against the keys, so keep DOMAIN_MAP keys lower-case.
Numeric codes work too (the CSV loader reads a column of 1, 2, 3 as integers):
key them by their text form, e.g. "1".
"""

from __future__ import annotations

from typing import NamedTuple

# A source category as it comes from DuckDB: text, or a code that CSV type
# detection read as a number or boolean.
SourceCategory = str | int | float | None  # bool is an int


class ClassificationInfo(NamedTuple):
    """Classification mapping for domain entities."""

    category: str
    quality_level: str
    risk_level: str
    description: str


# =============================================================================
# Domain Classification Map
# =============================================================================
# Customize this mapping for your domain.
# Keys are lower-case source categories, values are classification info.

# Column the CASE SQL reads; silver (and so bronze) must have it.
SOURCE_CATEGORY_COLUMN = "source_category"

DOMAIN_MAP: dict[str, ClassificationInfo] = {
    "type_a": ClassificationInfo(
        category="TYPE_A",
        quality_level="validated",
        risk_level="low",
        description="Type A entities",
    ),
    "type_b": ClassificationInfo(
        category="TYPE_B",
        quality_level="verified",
        risk_level="medium",
        description="Type B entities",
    ),
    "type_c": ClassificationInfo(
        category="TYPE_C",
        quality_level="certified",
        risk_level="high",
        description="Type C entities",
    ),
}

DEFAULT_INFO = ClassificationInfo(
    category="UNKNOWN",
    quality_level="raw",
    risk_level="informational",
    description="Unclassified",
)


def get_classification_info(source_category: SourceCategory) -> ClassificationInfo:
    """Get classification info for a source category.

    Matches like the generated CASE SQL: the value's text form, lower-cased,
    with no other normalisation (surrounding spaces are significant), and
    NULL/None gets the default.

    Args:
        source_category: Source category identifier.

    Returns:
        ClassificationInfo with classification fields.
    """
    if source_category is None:
        return DEFAULT_INFO
    return DOMAIN_MAP.get(str(source_category).lower(), DEFAULT_INFO)


# =============================================================================
# SQL CASE Statement Generation
# =============================================================================

def sql_string_literal(value: str) -> str:
    """Quote a value as a SQL string literal.

    Single quotes are doubled, the SQL standard escape that DuckDB uses;
    backslashes have no special meaning in DuckDB string literals.

    Args:
        value: Text to quote.

    Returns:
        The quoted literal, e.g. ``it's`` becomes ``'it''s'``.

    Raises:
        ValueError: If the value contains a NUL character.
    """
    if "\x00" in value:
        raise ValueError("SQL string literals cannot contain NUL characters")
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(name: str) -> str:
    """Quote a column name as a SQL identifier, doubling double quotes.

    Args:
        name: A single column name (not an expression or a dotted path).

    Returns:
        The quoted identifier, e.g. ``source_category`` becomes
        ``"source_category"``.

    Raises:
        ValueError: If the name is empty or contains a NUL character.
    """
    if not name or "\x00" in name:
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def generate_case_sql(
    mapping: dict[str, ClassificationInfo],
    input_col: str,
    output_field: str,
    default_value: str,
) -> str:
    """Generate SQL CASE statement from Python mapping.

    Keys, values and the default are emitted as escaped string literals and
    the input column as a quoted identifier, so mapping data cannot change
    the structure of the SQL. The column is cast to VARCHAR and lower-cased
    before matching, as in get_classification_info, so it may be text or a
    numeric code, and keys should be lower-case.

    Args:
        mapping: Classification mapping dictionary.
        input_col: Input column name.
        output_field: Which field to extract (category, quality_level, risk_level).
        default_value: Default value for unmatched cases.

    Returns:
        SQL CASE expression string (just the default literal if the mapping
        is empty, since CASE needs at least one WHEN).

    Raises:
        ValueError: If output_field is not a ClassificationInfo field.
    """
    if output_field not in ClassificationInfo._fields:
        raise ValueError(f"unknown ClassificationInfo field: {output_field!r}")

    column = sql_identifier(input_col)
    default = sql_string_literal(default_value)
    if not mapping:
        return default

    cases = []
    for key, info in mapping.items():
        value = getattr(info, output_field)
        cases.append(
            f"    WHEN {sql_string_literal(key)} THEN {sql_string_literal(value)}"
        )

    return f"""CASE lower(CAST({column} AS VARCHAR))
{chr(10).join(cases)}
    ELSE {default}
END"""


# Pre-generated SQL CASE statements (defaults come from DEFAULT_INFO)
CATEGORY_CASE_SQL = generate_case_sql(
    DOMAIN_MAP, SOURCE_CATEGORY_COLUMN, "category", DEFAULT_INFO.category
)

QUALITY_CASE_SQL = generate_case_sql(
    DOMAIN_MAP, SOURCE_CATEGORY_COLUMN, "quality_level", DEFAULT_INFO.quality_level
)

RISK_CASE_SQL = generate_case_sql(
    DOMAIN_MAP, SOURCE_CATEGORY_COLUMN, "risk_level", DEFAULT_INFO.risk_level
)
