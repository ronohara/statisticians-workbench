"""The one timestamp form the API emits.

    >>> iso_utc(datetime(2026, 11, 8, 8, 40, 24, 878556, tzinfo=timezone.utc))
    '2026-11-08T08:40:24.878Z'

THE FORM, AND WHY IT IS THIS ONE

ISO 8601 with a ``T`` separator, three fraction digits, and ``Z`` for a UTC instant.
Decided on 2026-11-08 (Item 12a of the timestamp plan) from three constraints that each
leave one choice:

- **An offset is mandatory.** A string without one is a wall clock, and a browser reads
  that as *local* — measured, seven hours early for a UTC instant written on a machine
  set to Asia/Bangkok. A naive-looking string is not a neutral absence of information; it
  is a claim that the reader's zone applies.

- **``Z`` rather than ``+00:00``.** Both are valid ISO 8601 and they are different
  strings, so one has to be chosen. JavaScript's ``Date.prototype.toISOString()`` emits
  ``Z`` with three digits, which means the frontend receives exactly the shape it would
  have produced itself, and a value that round-trips through the browser comes back
  byte-identical.

- **Three fraction digits, not six.** Milliseconds are what ``toISOString()`` gives.
  The extra three are noise on a display timestamp and a second place for two backends
  to disagree — which is precisely what they did before this module existed.

WHY IT IS ONE MODULE

Before Item 12b this tree had four ``_iso`` definitions in two behaviours (three files
emitting three digits, ``admin/users.py`` emitting six-or-none), plus ten call sites
building a response field with ``str(datetime)`` — which emits a *space* separator and an
offset, a third shape. On the Go side the same drift had produced eight helpers over 85
call sites, two of them independent ports of the same function that disagreed with each
other.

The rule this module exists to enforce is the one its predecessors kept rediscovering:
**a formatter that exists twice will eventually exist in two versions.** A caller that
needs a different string has found a *rendering* requirement, and the place for that is
the frontend, not a second serialiser here.

WHAT IT DOES NOT DO

It does not choose a form per caller, and it does not take a format string. It also does
not decide *whether* to send a timestamp — that is the caller's schema.
"""

from datetime import datetime, timezone
from typing import Optional

__all__ = ["iso_utc"]

#: The wire form. ``.000`` is part of it: a whole second keeps its milliseconds so that
#: every timestamp in a response has the same length and the same shape, and so that a
#: test can assert the format with one regex rather than two.
_LAYOUT = "%Y-%m-%dT%H:%M:%S.%f"


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """Render an instant as the API's timestamp string, or ``None`` for a null column.

    Accepts a naive datetime and treats it as UTC, because a ``timestamptz`` column that
    somehow arrives without a tzinfo still holds an instant at UTC — the alternative,
    raising, would turn a display concern into a 500. Every column in this schema is
    ``timestamptz`` since the timestamp plan's Item 7, so this path exists for defensive
    reasons alone.

    Local-aware values are converted rather than rejected: the stored instant is what
    matters, and which zone a driver chose to label it with is not the caller's business.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    # strftime, not isoformat(): isoformat emits six digits, or none at all for a whole
    # second, and truncating its output by slicing is what the previous copies did.
    return value.astimezone(timezone.utc).strftime(_LAYOUT)[:-3] + "Z"
