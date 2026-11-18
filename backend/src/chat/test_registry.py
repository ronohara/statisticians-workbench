"""
Test registry — the one place a model suitability test is declared.

Every test the AI Test page can run is declared here exactly once. Adding a test
is one entry in TESTS plus its probe function; nothing else needs to change — no
migration, no new column, no change to either backend's scan code — because a
result is stored as one jsonb object keyed by test id rather than in a column per
test.

The ids are data, never display text:

  - They are the keys a stored result is filed under. Renaming one orphans every
    result already recorded against it. The record that holds them is not named
    here, deliberately: naming it is how the previous version of this docstring
    went stale — the column it named was dropped — and where results live is a
    schema question that can change without the ids changing.
  - They are NOT translated. The page's label for a test is a frontend
    translation key resolved from the id; the id itself must stay stable in
    every language.

`probe` names the function that runs the test rather than importing it, so that
the registry can be read — by the writer, by the page, by a parity case — before
any probe exists. Dispatch resolves the name against the probe module at call
time.

`duration` is an estimate for the interface, not a limit: "seconds" for a test
that is one or two provider round trips, "minutes" for the one that drives a
whole concierge turn. The page uses it to warn before a catalogue-wide run.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TestDefinition:
    """One suitability test: what runs it, and what running it costs."""

    test_id: str
    probe: str
    duration: str
    requires_dataset: bool


# The registered tests. Order is presentation order on the AI Test page.
TESTS = {
    "tools": TestDefinition(
        test_id="tools",
        probe="probe_tools",
        duration="seconds",
        requires_dataset=False,
    ),
    "competence": TestDefinition(
        test_id="competence",
        probe="probe_competence",
        duration="seconds",
        requires_dataset=False,
    ),
    "turn": TestDefinition(
        test_id="turn",
        probe="probe_turn",
        duration="minutes",
        requires_dataset=True,
    ),
}


def is_registered(test_id: str) -> bool:
    """True when `test_id` is a test this build knows how to run and store."""
    return test_id in TESTS


def get(test_id: str) -> Optional[TestDefinition]:
    """The definition for `test_id`, or None when it is not registered."""
    return TESTS.get(test_id)


def all_ids() -> list:
    """Every registered test id, in presentation order."""
    return list(TESTS.keys())
