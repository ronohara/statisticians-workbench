"""
The synthetic dataset the `turn` test runs against (plan Item 9b).

The user's instruction, 2026-10-30: "have a synthetic dataset - it can have the
full complement of datatypes needed to exercise model competence - run the turn,
drop it ... use the workbench_data database to hold this - and self-clean".

WHY IT LIVES IN `workbench_data`
--------------------------------
That is where the product keeps generated tables — uploads, cleaned copies,
materialised virtual datasets — and where the data pool already points. A test
table there is created and dropped by the same machinery the product uses, so
the test exercises the real path rather than a parallel one.

WHAT IT HOLDS
-------------
One table with the types a model has to reason about: text, integer, numeric,
date, timestamp, boolean, and a low-cardinality categorical code stored as an
integer. That last one is deliberate — the guide records `orders.order_status`
being stored as `integer` and every consumer treating it as a numeric measure.
A model that calls `mean` on `order_status` has made exactly that mistake, and
the dataset is shaped so the mistake is available to be made.

THE RUN IDENTITY IS IN THE NAME
-------------------------------
Each run's table is named from a per-run identifier, so two concurrent runs
cannot collide and a crashed run leaves an identifiable table rather than a
mystery. `run_id` is also what the drop uses, so a run can only remove its own
table.

WHO OWNS IT
------------
Every object the application creates in `workbench_data` lives in the schema of
the account that owns it (`u_<user_id>`), and this table is no exception. The
owner is `admin@example.com` — a test artifact belongs to the account that runs
the tests, not to whoever happened to press a button, so an orphaned table is
always findable in one known schema. A hard kill can therefore leave an owned,
orphaned table; the reconciliation sweep tidies it up, which is the same
treatment uploads get.

SELF-CLEANING IS A `finally`, NOT A HOPE
----------------------------------------
`with synthetic_dataset()` yields the dataset and drops the table however the
block exits — success, exception, or cancellation. A pre-existing table with a
run's name is refused rather than reused, so a collision is a loud failure
rather than a silent one.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime

from src import postgres_data_manager

logger = logging.getLogger(__name__)

# The table's shape. Ordered, because the CREATE statement follows this order and
# a model reading the schema sees it this way.
COLUMNS = ["order_id", "region", "amount", "order_date", "created_at", "is_shipped", "order_status"]

# Enough rows that a grouping is meaningful, few enough to create and drop in a
# second. Values are fixed, not random: the same dataset every run is what makes
# results comparable between models and between days.
_ROWS = [
    {"order_id": 1, "region": "north", "amount": 120.50, "order_date": date(2026, 1, 5),
     "created_at": datetime(2026, 1, 5, 9, 30), "is_shipped": True, "order_status": 1},
    {"order_id": 2, "region": "south", "amount": 80.00, "order_date": date(2026, 1, 6),
     "created_at": datetime(2026, 1, 6, 10, 15), "is_shipped": True, "order_status": 1},
    {"order_id": 3, "region": "north", "amount": 245.75, "order_date": date(2026, 1, 7),
     "created_at": datetime(2026, 1, 7, 11, 0), "is_shipped": False, "order_status": 2},
    {"order_id": 4, "region": "east", "amount": 60.25, "order_date": date(2026, 1, 8),
     "created_at": datetime(2026, 1, 8, 14, 45), "is_shipped": True, "order_status": 1},
    {"order_id": 5, "region": "west", "amount": 310.00, "order_date": date(2026, 1, 9),
     "created_at": datetime(2026, 1, 9, 8, 20), "is_shipped": False, "order_status": 3},
    {"order_id": 6, "region": "south", "amount": 95.10, "order_date": date(2026, 1, 10),
     "created_at": datetime(2026, 1, 10, 16, 5), "is_shipped": True, "order_status": 2},
]

# The column types the table must end up with. Asserted after creation rather
# than assumed: `create_table_from_rows` infers from values, and a wrong
# inference would quietly weaken the test.
EXPECTED_TYPES = {
    "order_id": "bigint",
    "region": "text",
    "amount": "double precision",
    "order_date": "date",
    "created_at": "timestamp without time zone",
    "is_shipped": "boolean",
    "order_status": "bigint",
}


# The account that owns the test dataset. Fixed rather than "whoever ran it",
# so every test table lives in one schema and an orphan is easy to find.
DEFAULT_OWNER_EMAIL = "admin@example.com"

_db_pool = None


def set_db_pool(pool):
    """Share the main workbench pool, wired in main.py like every other router."""
    global _db_pool
    _db_pool = pool


async def resolve_owner_id(email: str = DEFAULT_OWNER_EMAIL) -> str:
    """The user id that owns the test dataset."""
    if _db_pool is None:
        raise RuntimeError("workbench pool is not initialised")
    async with _db_pool.acquire() as conn:
        owner = await conn.fetchval('SELECT id FROM "User" WHERE email = $1', email)
    if owner is None:
        raise RuntimeError(f"test dataset owner {email!r} does not exist")
    return owner


def table_name_for(run_id: str, owner_id: str) -> str:
    """The qualified table name for a run: owned, and identifiable as ours."""
    return f"u_{owner_id}.ai_test_dataset_{run_id}"


@asynccontextmanager
async def synthetic_dataset(run_id=None):
    """Create the dataset, yield it in the concierge's shape, drop it.

    Yields a dict in the form `routers/aitesting/tools.py` reads:

        {"table": <name>, "columns": [{"name", "type"}, …], "rows": [...]}

    The table is dropped on every exit path. If the drop itself fails, that is
    logged rather than raised: an exception raised from a `finally` would mask
    the real failure that caused the exit.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    owner_id = await resolve_owner_id()
    table = table_name_for(run_id, owner_id)

    # A collision is refused, not reused. `create_table_from_rows` would fail on
    # an existing table anyway, but saying so here names the reason.
    if await _table_exists(table):
        raise RuntimeError(
            f"synthetic dataset table {table!r} already exists; refusing to reuse it"
        )

    dataset = None
    try:
        await postgres_data_manager.create_table_from_rows(COLUMNS, _ROWS, table)

        types = await _column_types(table)
        wrong = {
            column: (types.get(column), expected)
            for column, expected in EXPECTED_TYPES.items()
            if types.get(column) != expected
        }
        if wrong:
            raise RuntimeError(f"synthetic dataset has unexpected column types: {wrong}")

        # `dropped` starts False and is flipped by the cleanup, so a caller can
        # tell "the drop happened" from "the drop was attempted". Logging a
        # failure is not reporting it.
        dataset = {
            "table": table,
            "columns": [{"name": c, "type": EXPECTED_TYPES[c]} for c in COLUMNS],
            "rows": [dict(row) for row in _ROWS],
            "dropped": False,
        }
        logger.info("synthetic dataset created table=%s rows=%d", table, len(_ROWS))
        yield dataset
    finally:
        try:
            await postgres_data_manager.drop_table(table)
            if dataset is not None:
                dataset["dropped"] = True
            logger.info("synthetic dataset dropped table=%s", table)
        except Exception:
            # Deliberately swallowed after logging: this runs during exception
            # propagation, and raising here would replace the real failure.
            logger.exception("synthetic dataset drop FAILED table=%s — left behind", table)


async def _table_exists(table: str) -> bool:
    pool = postgres_data_manager.get_data_pool()
    if pool is None:
        raise RuntimeError("workbench_data pool is not initialised")
    schema, bare = _split(table)
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = $1 AND table_name = $2)",
            schema, bare,
        )


def _split(table: str):
    """(schema, bare table) — the qualified name is the only form we use."""
    schema, _, bare = table.partition(".")
    if not bare:
        raise ValueError(f"expected a schema-qualified table name, got {table!r}")
    return schema, bare


async def _column_types(table: str) -> dict:
    pool = postgres_data_manager.get_data_pool()
    schema, bare = _split(table)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = $1 AND table_name = $2",
            schema, bare,
        )
    return {r["column_name"]: r["data_type"] for r in rows}
