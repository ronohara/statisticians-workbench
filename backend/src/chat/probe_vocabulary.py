"""
Probe vocabulary — the outcome type, its closed set, and the transport error.

This is the vocabulary a probe *speaks*, kept apart from any probe that speaks
it. It lives in its own module because two modules need it from opposite sides:
`chat/model_probe.py` returns these values, and `routers/aitesting/concierge.py`
returns them too, while `model_probe.probe_turn` calls into the concierge. Sharing
the vocabulary through `model_probe` would make the concierge import the module
that imports the concierge — an import cycle.

Python tolerates that cycle only by deferring one import into a function body,
which is exactly what the project's no-lazy-loading rule forbids: a deferred
import has no Go counterpart, so the port would have to re-derive a dependency
edge the Python source declined to state. Go rejects package cycles outright, so
the cycle is not a porting obstacle to work around — it is a module boundary in
the wrong place. Moving the vocabulary here removes it in both languages.

The reason a value is not a boolean, and why a transport failure is not a verdict,
are documented where they are decided: `model_probe`'s module docstring.
"""

from dataclasses import dataclass, field

# Per-call ceiling. Generous because a CPU-hosted 27B model takes minutes, and a
# probe that times out on a slow-but-good model would record a false failure.
DEFAULT_TIMEOUT = 300.0

# The outcomes, i.e. the reason keys a stored result is filed under. Every probe
# returns exactly one of these, and nothing outside the set is ever recorded.
OK = "ok"
DESCRIBES = "describes"
FABRICATES = "fabricates"
# `vocabulary` was one value covering two different faults, and they send the user to
# different fixes, so it is now two:
#
#   UNKNOWN_MEMBER  the model named something that does not exist — a column, a table,
#                   a dataset. The fix is to read the schema before naming a part of it.
#   INVALID_CHOICE  the model chose a value outside a declared set — an operation from a
#                   closed list. The fix is to pick one of the listed options.
#
# Both are the model's fault and both are failures, so both map to `fail`; the split is
# about what the record tells a reader, not about severity.
#
# KNOWN GAP, recorded rather than papered over: the turn tools can also answer
# `column_required` — the model named no column at all where one is required. That is a
# third fault (an incomplete call, not a wrong member and not a wrong choice) and it is
# currently classified UNKNOWN_MEMBER. It has no observed instance; when one appears it
# needs its own value rather than a redefinition of this one.
UNKNOWN_MEMBER = "unknown_member"
INVALID_CHOICE = "invalid_choice"
UNSTABLE = "unstable"

# A SIXTH OUTCOME THAT IS NOT A REASON KEY.
#
# `unstable` was carrying two unrelated facts. A repeat loop, or an answer that
# names the wrong tool, is something the model DID — a verdict, and recording it
# is the point of the instrument. A run that produced nothing because it spent its
# whole token budget thinking is a fact about the RUN, and design rule 3 says it
# must not touch the model record: "a token budget exhausted before the model
# answered ... records only its duration". Measured, not supposed:
# deepseek-r1:8b spent its entire 1024-token budget on this machine's CPU and
# answered nothing.
#
# Under one constant those two arrived identically, so a writer with the item's
# own rule — "an outcome means both writes" — would have recorded a slow machine
# as a model that cannot act, permanently. That is the fault rule 3 exists to
# prevent, and it is why this is a separate constant rather than a comment.
#
# It is deliberately NOT in the mapping below: `state_for` raises KeyError for it,
# which is its existing behaviour for anything outside the closed set. An unmapped
# outcome is a programming error, and silently storing it as a failure would
# invent the verdict this constant exists to withhold.
INCONCLUSIVE = "inconclusive"

# The state a reason maps to. Only `ok` is a pass; every other reason is a
# failure, because each names something the model did instead of what the test
# asked for. Single-sourced here so the endpoint does not re-state the rule and a
# fixture can assert the mapping without a database or a model.
_REASON_TO_STATE = {
    OK: "pass",
    DESCRIBES: "fail",
    FABRICATES: "fail",
    UNKNOWN_MEMBER: "fail",
    INVALID_CHOICE: "fail",
    UNSTABLE: "fail",
}
# INCONCLUSIVE is absent on purpose — see its declaration. `state_for` refusing it
# is the mechanism that keeps a run which never reached an answer out of the model
# record, so the omission is the rule rather than an oversight.


def state_for(outcome: str) -> str:
    """The recorded state for a probe outcome: `pass` for ok, `fail` otherwise.

    Raises KeyError for a value outside the closed set, which is deliberate: an
    unmapped outcome is a programming error, and silently storing it as a
    failure would invent a verdict.

    `INCONCLUSIVE` is outside the set by design, so this raises for it. That is
    the whole point: a run the model never finished has no state, and a caller
    that asks for one has asked the wrong question rather than found a bug in the
    mapping. A writer must therefore ask `state_for` only when it intends to
    record a verdict, and check for `INCONCLUSIVE` first when it does not.
    """
    return _REASON_TO_STATE[outcome]


class ProbeTransportError(Exception):
    """The model was never asked, or never answered — so there is no verdict.

    Raised for a missing key, an unknown provider, a refused connection, a DNS
    failure, or a timeout that persisted through the retries. The caller must
    leave the stored result untouched: recording `fail` here would mark a good
    model bad because a host was down, and the record would outlive the incident.
    """

    def __init__(self, detail: str, failure_class: str = "other", http_status: int | None = None):
        """`failure_class` says HOW it failed — plan Item 5.

        It travels beside the detail rather than inside it. A detail string is for a
        support conversation; the class is what a user is told, and what the route
        selects a message by. Before this, the class had to be guessed from the text,
        which is how a provider answering 400 "not a valid model ID" came to be
        reported as unreachable.

        Defaults to `other` rather than raising when absent, because a transport
        failure with no class is still a transport failure — it is reported truthfully
        as unclassified rather than suppressed.
        """
        self.detail = detail
        self.failure_class = failure_class
        self.http_status = http_status
        super().__init__(detail)


@dataclass
class ProbeOutcome:
    """What a probe observed, and the reason key that names it."""

    outcome: str
    detail: str
    observations: dict = field(default_factory=dict)
