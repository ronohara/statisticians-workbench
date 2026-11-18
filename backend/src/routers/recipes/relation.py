"""
SQL relation abstraction for the recipe stream.

A Relation is a reference to the table the recipe stages read from: either the
raw base table (un-prepared data) or a materialized TEMP table (prepared data,
built in Item 19). Both are just a table name plus metadata — no CTE/subquery.

The relation lives on the single held data-pool connection for the recipe
execution (one PostgreSQL session), so its table is visible to every stage.
"""

from dataclasses import dataclass
from typing import List

from src.routers.datasets.sql_dialect import quote_table


@dataclass(frozen=True)
class Relation:
    """A reference to a table in the recipe stream."""

    storage_type: str
    columns: List[str]
    table_name: str


def relation_source(relation: Relation) -> str:
    """Return the quoted (possibly schema-qualified) table name to place after ``FROM``."""
    return quote_table(relation.table_name, relation.storage_type)
