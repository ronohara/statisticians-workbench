"""
The one database pool, and the rule that every module reads it from here.

============================================================
WHY THIS FILE EXISTS — the incident, recorded in full
============================================================

On 2026-11-01, `POST /api/user/ai-connections/4/models/fetch` returned

    400  {"error": "user.failed_to_fetch_models", "message": "Failed to fetch models"}

The generic message came from the handler's `except Exception:` tail. The exception it
was swallowing was

    NameError: name '_db_pool' is not defined

raised inside `_fetch_models_from_provider` in `routers/user/model_discovery.py`, at
its first line that touches a pool:

    async with _db_pool.acquire() as conn:

That module declared no `_db_pool`, defined no `set_db_pool`, and `main.py` never
mentioned it. It had been written as though the pool were a process-wide global —
which is how the Go port works — but in Python a module-level name exists only if
that module declares it and something assigns it.

Nothing caught it. Not the tests: the five suites that exercise discovery build their
own connection and never go through the module global. Not the import: the failure is
inside a function body, so the module imported cleanly. Not a compiler: Python has
none. It surfaced when a button was pressed, in a 400 that named no cause.

============================================================
THE TWO CONVENTIONS THAT HAD GROWN APART
============================================================

**Go** has one package-level `internal/db.Pool`, assigned once by `db.Init` and read
directly by 74 files. There is no wiring to forget, because there is no wiring. A
missing pool is a build error — you either imported the package or you did not.

**Python** had the opposite: 56 modules each declared their own `_db_pool = None` and
exported a `set_db_pool(pool)`, which `main.py` called once per module under 28
distinct aliases. Where a package held several sub-modules, the package's setter
fanned out to each by hand — `routers/datasets/__init__.py` calls fourteen of them,
one line each.

So the Python form required two edits, in two files, with nothing checking that the
second had been made:

    1. declare `_db_pool` and `set_db_pool` in the module          (easy to do)
    2. add the module's setter to its package's fan-out            (easy to forget)

`model_discovery` was the module where step 2 was forgotten. The failure mode is not
"someone wrote bad code"; it is that the convention had a second, unverified step, and
a hand-maintained list is a list that eventually disagrees with the tree.

============================================================
WHY THAT MATTERED BEYOND ONE BUG
============================================================

The project's porting rule is that the Python reference and the Go port are read side
by side, line by line, and that a name held by both is spelled identically. A reviewer
putting `_fetch_models_from_provider` beside `fetchModelsFromProvider` sees

    async with _db_pool.acquire() as conn:          # Python
    ctx context.Context, pool *pgxpool.Pool, ...     # Go

and cannot tell whether the Python one is wired. The name *looks* like the Go global
and means something else entirely. In that state the cheapest fidelity check the
project has — reading the two files together — stops working, which is a larger cost
than the bug.

============================================================
THE RULE NOW
============================================================

    Every module reads the pool from this one file. No module declares its own.

`main.py` assigns it once, in the lifespan hook, after `create_pool` succeeds. That is
the whole wiring: one assignment, one place, findable with one grep. The count of
things that can be forgotten goes from 56 fan-out lines to zero.

Equivalences to the port, for the side-by-side reading:

    Python                  Go
    db.pool()               db.Pool
    db.set_pool(pool)       db.Init(...) assigns db.Pool

============================================================
WHY `pool()` IS A FUNCTION AND NOT `pool` AN ATTRIBUTE
============================================================

The obvious shape is a module attribute — `db.pool.acquire()` — which would read closer
to Go's `db.Pool`. It is not used, because exposing it as an attribute would need
PEP 562 `__getattr__` to resolve lazily, and the project's No Lazy Loading rule forbids
module-level `__getattr__` outright: it is a deferred resolution with no Go counterpart,
and the port would have to re-derive the edge. A plain function has the same call graph,
is static, and ports to a plain function.

A second reason, and the one that matters for this file's purpose: a function can
*explain itself* when the pool is missing. Reading an attribute that is `None` gives
`AttributeError: 'NoneType' object has no attribute 'acquire'`, which names the symptom.
`pool()` raises `PoolNotInitialised` with the reason. On a defect whose whole cost was
that nobody could see the cause, the error is part of the fix.

============================================================
WHAT IS NOT DONE HERE, AND IS HONEST ABOUT IT
============================================================

The mechanism is in place and `main.py` assigns it. The 56 per-module setters still
exist and still work — they are not removed by this file, and a half-migrated tree
holds both conventions at once, which is the ambiguity this file was written to end.

Migration is mechanical: in each module, delete `_db_pool = None` and `set_db_pool`,
import `from src import db`, and call `db.pool()` where it called `_db_pool`. The
modules already migrated are listed in `MIGRATED` below so the remaining set is
knowable rather than guessed.

Do it module by module, each verified, rather than as one sweeping rewrite: a
mechanical change applied to 67 files in one pass is exactly the change where a
silently-wrong edit survives, because nothing distinguishes "correctly migrated" from
"migrated into a different bug".
"""

from typing import Optional

import asyncpg

#: The pool, assigned once by `main.py`. `None` until the lifespan hook has run.
_pool: Optional[asyncpg.Pool] = None

#: Modules that read the pool from here. Grows as the per-module setters are removed;
#: a module absent from this list still uses its own `_db_pool` global.
MIGRATED: tuple[str, ...] = (
    "src.routers.user.model_discovery",
)


class PoolNotInitialised(RuntimeError):
    """The pool was read before something assigned it.

    Raised instead of letting an `AttributeError` on `None` reach the caller, because
    the AttributeError names the symptom and this names the cause. If this fires, the
    pool was either never created — check the startup log for "Database pool
    initialized." — or a module was imported and used before the lifespan hook ran.
    """


def set_pool(pool: asyncpg.Pool) -> None:
    """Assign the pool. Called once, by `main.py`, after `create_pool` succeeds.

    Not called by modules, not called by tests that want their own pool. A test that
    needs a different pool should call this — it is the one seam — and restore the
    previous value afterwards.
    """
    global _pool
    _pool = pool


def pool() -> asyncpg.Pool:
    """The process's database pool.

    Equivalent to Go's `db.Pool`. Raises `PoolNotInitialised` rather than returning
    None, so a missing assignment fails at the point of use with an explanation
    instead of surfacing as an AttributeError three frames away.
    """
    if _pool is None:
        raise PoolNotInitialised(
            "the database pool has not been assigned: main.py assigns it in the "
            "lifespan hook after create_pool succeeds. If this is a test, call "
            "db.set_pool(...) first."
        )
    return _pool


def is_initialised() -> bool:
    """Whether a pool has been assigned. For health checks and startup assertions."""
    return _pool is not None
