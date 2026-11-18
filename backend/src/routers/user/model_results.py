"""
The two result writers, and the gate between them (plan Item 20b).

A capability result describes the MODEL and is written to
`LLMModel."modelTestResults"`. A performance measurement describes the SERVER and
is written to `ConnectionModelIntersect."connectionTestResults"`. The same model
measured fast on one host and slow on another is not a contradiction — that is the
whole reason the two facts have separate homes, and why no writer here can put one
in the other's place.

WHY TWO WRITERS AND ONE GATE

Two writers, because the two rows are different tables with different lifecycles: a
model outlives its connections, and a connection's findings go with it when the
connection does. One gate, because which facts may be recorded must not be decided
twice. `record_result` is the gate; the two writers below it are the only code that
touches either column, and nothing else in the backend composes its own UPDATE.

THE RULE, AS ONE BRANCH

    a state means both writes; no state means the duration only.

`chat/probe_vocabulary.state_for` raises `KeyError` for `INCONCLUSIVE`, which is how
a run the model never finished is kept out of the model record. Item 20a put that
refusal in the vocabulary precisely so this function could not get it wrong by
forgetting to check: asking for a state is asking "may this be recorded as a verdict",
and the vocabulary answers.

A transport failure never reaches either writer as an outcome — the probe raises
`ProbeTransportError` instead of returning one, and the endpoint catches it. But it
is still recorded as a duration on the connection, because how long a connection took
to fail is a fact about the connection and about nothing else. That is what
`record_performance` is for, and it is why it accepts an outcome that the model
writer would refuse.

WHAT THE DATABASE ENFORCES, AND WHAT IT CANNOT

The column is jsonb with an object CHECK, so the top-level shape is enforced. The
inner keys are runtime data and no constraint can see them — which is why the three
refusals live here: an unregistered test id would create a phantom test no page lists
and no probe can fill; an outcome outside the closed set has no state to record; and a
capability result must be attributable, because the row is shared across a group and
an unattributed verdict cannot be traced to the machine that produced it.

THE MERGE IS THE MECHANISM

`column || jsonb_build_object(test_id, entry)` is a shallow merge: it replaces the key
for that one test and leaves every other key exactly as it was. A re-run of `tools`
cannot disturb `competence` or `turn`. A writer that replaced the whole object would
silently erase two results every time a third was recorded, which is the run-state bug
this project has already paid for once.

`testedAt` is stamped by the statement from the database clock and merged *after* the
caller's fields, so no caller can backdate a result or shadow the stamped value.
"""

import logging

from src.chat import probe_vocabulary, test_registry
from src.routers.user.translations import USER

logger = logging.getLogger(__name__)


class ResultWriteRefused(Exception):
    """A refused write, carrying the declared `TranslationKey` itself.

    The key travels as the `TranslationKey` object, never as a bare string: the
    caller renders it with `t(pool, language, err.key, **err.kwargs)`, and a string
    would have to be re-mapped through `USER[...]` at the call site — the
    duplicate-name drift the translation rules forbid.
    """

    def __init__(self, key, **kwargs):
        self.key = key
        self.kwargs = kwargs
        super().__init__(key.key)


class UnknownModelError(ResultWriteRefused):
    """No `LLMModel` row with that id. A model nobody can select is not a typo to ignore."""

    def __init__(self, model_id):
        super().__init__(USER["api.user.model_not_found"], provider=model_id, model=model_id)


class UnknownConnectionModelError(ResultWriteRefused):
    """No `ConnectionModelIntersect` row for that pair.

    Distinct from `UnknownModelError`: the model exists, but this connection has not
    discovered it — so there is nowhere to record what the connection measured. The
    caller's fix is a discovery run, not a different model id.
    """

    def __init__(self, connection_id, model_id):
        super().__init__(
            USER["api.user.model_not_found"],
            provider=str(connection_id),
            model=model_id,
        )


def _check_writable(test_id, outcome, tested_by):
    """The three refusals both writers share, in one place.

    Returns the state `outcome` names. Raises `ResultWriteRefused` for an
    unregistered test, an outcome with no state, or a missing attribution — each
    before any statement runs, so a refusal cannot leave a partial write.
    """
    if not test_registry.is_registered(test_id):
        raise ResultWriteRefused(
            USER["api.user.unknown_test_id"],
            test=test_id,
            known=", ".join(test_registry.all_ids()),
        )

    try:
        state = probe_vocabulary.state_for(outcome)
    except KeyError:
        # The outcome is outside the closed set — either INCONCLUSIVE, which is a
        # fact about the run, or a value invented at some call site. Neither may
        # become a verdict, and neither may be silently dropped: the caller asked
        # to record a result and is being told it cannot.
        raise ResultWriteRefused(
            USER["api.user.invalid_test_state"],
            state=outcome,
            allowed=", ".join(
                [probe_vocabulary.OK, probe_vocabulary.DESCRIBES,
                 probe_vocabulary.FABRICATES, probe_vocabulary.UNKNOWN_MEMBER,
                 probe_vocabulary.INVALID_CHOICE, probe_vocabulary.UNSTABLE]
            ),
        )

    if not tested_by or not str(tested_by).strip():
        # The row is shared across a group (design rule 4: any user who can read the
        # connection may record). An unattributed result cannot be traced to the
        # machine that produced it, and the record outlives the incident.
        raise ResultWriteRefused(USER["api.user.test_attribution_required"])

    return state


async def record_capability(pool, model_id, test_id, outcome, duration_ms, tested_by,
                            evidence=None, conn=None):
    """Record one capability result against a model. Returns the stored entry.

    `duration_ms` is written here as well as on the connection: it is part of the
    evidence for the verdict — a result obtained in 189 s is a different observation
    from one obtained in 4 s even when both say `ok` — but the *performance*
    judgement is the connection's, computed at read time against the user's
    threshold.

    `conn` lets the caller supply a connection that already has a transaction open.
    `record_result` does exactly that, so the capability row and the performance row
    it writes next commit or roll back together; see the note there. Omitted, this
    acquires its own connection and runs as a single statement, unchanged.

    Raises `ResultWriteRefused` for a refused write and `UnknownModelError` when no
    such model exists.
    """
    state = _check_writable(test_id, outcome, tested_by)

    entry = {
        "state": state,
        "reason": outcome,
        "testedBy": tested_by,
        "durationMs": int(duration_ms),
    }
    if evidence is not None:
        entry["evidence"] = evidence

    if conn is None:
        async with pool.acquire() as acquired:
            stored_entry = await _apply_capability(acquired, model_id, test_id, entry)
    else:
        stored_entry = await _apply_capability(conn, model_id, test_id, entry)

    logger.info(
        "capability recorded model=%s test=%s state=%s reason=%s by=%s",
        model_id, test_id, state, outcome, tested_by,
    )
    return stored_entry


async def _apply_capability(conn, model_id, test_id, entry):
    """The capability UPDATE itself, on a connection the caller already holds."""
    # Bind the PLAIN OBJECT, never json.dumps() of it. The pool registers json/jsonb
    # codecs whose encoder is json.dumps, so a pre-serialised string is encoded twice
    # and arrives as a jsonb *string*; `jsonb || jsonb` on a scalar then produces an
    # ARRAY instead of merging an object, and the result is silently valid-but-wrong.
    row = await conn.fetchrow(
        'UPDATE public."LLMModel" '
        'SET "modelTestResults" = COALESCE("modelTestResults", \'{}\'::jsonb) '
        '                       || jsonb_build_object('
        '                            $2::text, '
        '                            $3::jsonb || jsonb_build_object(\'testedAt\', to_jsonb(NOW()))'
        '                          ), '
        '    "updatedAt" = NOW() '
        'WHERE id = $1 '
        'RETURNING "modelTestResults"',
        model_id,
        test_id,
        entry,
    )

    if row is None:
        # An UPDATE that matches nothing returns success. Refused rather than
        # ignored, or the caller records a result that exists nowhere.
        raise UnknownModelError(model_id)

    stored = row["modelTestResults"] or {}
    return stored.get(test_id, entry)


async def record_performance(pool, connection_id, model_id, test_id, duration_ms, outcome,
                             conn=None, failure_class=None):
    """Record one measurement against a connection-model pairing.

    Accepts an `INCONCLUSIVE` outcome and a transport failure, because both are
    facts about the server: how long it took to fail, and that it failed. Nothing
    here can become a capability verdict — the caller records that separately, and
    `record_capability` is the only path to it.

    Unlike `record_capability` there is no attribution: a duration is not a claim
    about a model, and the connection is already owned.

    `conn` is the same door `record_capability` offers: supply a connection with a
    transaction already open and this joins it instead of acquiring its own.
    """
    if not test_registry.is_registered(test_id):
        raise ResultWriteRefused(
            USER["api.user.unknown_test_id"],
            test=test_id,
            known=", ".join(test_registry.all_ids()),
        )

    entry = {
        "durationMs": int(duration_ms),
        "outcome": outcome,
    }
    # HOW it failed, beside how long it took (plan Item 5 of
    # workbench-AI-timeout-policy-plan.html).
    #
    # It is not a verdict and cannot become one: `state_for` refuses anything outside
    # the reason vocabulary, and a failure class is not in it, so a class written here
    # can never be read back as `pass` or `fail`. What it gives a support conversation
    # is the difference between "it timed out" and "nothing was listening".
    #
    # Only written when supplied, so a successful run's entry is byte-identical to
    # what it was before.
    if failure_class:
        entry["failureClass"] = failure_class

    if conn is None:
        async with pool.acquire() as acquired:
            return await _apply_performance(
                acquired, connection_id, model_id, test_id, entry
            )
    return await _apply_performance(conn, connection_id, model_id, test_id, entry)


async def _apply_performance(conn, connection_id, model_id, test_id, entry):
    """The performance UPDATE itself, on a connection the caller already holds."""
    row = await conn.fetchrow(
        'UPDATE public."ConnectionModelIntersect" '
        'SET "connectionTestResults" = COALESCE("connectionTestResults", \'{}\'::jsonb) '
        '                              || jsonb_build_object('
        '                                   $3::text, '
        '                                   $4::jsonb || jsonb_build_object(\'at\', to_jsonb(NOW()))'
        '                                 ) '
        'WHERE "connectionId" = $1 AND "modelId" = $2 '
        'RETURNING "connectionTestResults"',
        connection_id,
        model_id,
        test_id,
        entry,
    )

    if row is None:
        raise UnknownConnectionModelError(connection_id, model_id)

    stored = row["connectionTestResults"] or {}
    return stored.get(test_id, entry)


async def record_result(pool, model_id, connection_id, test_id, outcome, duration_ms,
                        tested_by, evidence=None, failure_class=None):
    """The gate. One call site decides what is written where.

    `outcome` is either a probe's reason key or `INCONCLUSIVE`. The branch is written
    once, here, so a future test cannot be added with only half the rule:

        a state means both writes; no state means the duration only.

    Returns `(capability_entry_or_None, performance_entry)`.
    """
    try:
        state = probe_vocabulary.state_for(outcome)
    except KeyError:
        state = None

    if state is None:
        # No verdict. The connection still learns how long the run took, and the
        # model record is untouched — not written as `unknown`, not written at all.
        if test_registry.is_registered(test_id):
            performance = await record_performance(
                pool, connection_id, model_id, test_id, duration_ms, outcome,
                failure_class=failure_class,
            )
            return None, performance
        # An unregistered test id is refused by the capability writer's rules even
        # when there is no capability to write: recording a duration under a test
        # that does not exist is the phantom-key problem in a different column.
        raise ResultWriteRefused(
            USER["api.user.unknown_test_id"],
            test=test_id,
            known=", ".join(test_registry.all_ids()),
        )

    # BOTH WRITES IN ONE TRANSACTION. A verdict and the duration that produced it are
    # one fact about the connection, and they live in two tables. Written separately,
    # a failure between them commits the capability row and then refuses the
    # performance row — so the caller is told nothing was recorded while the model
    # record already claims a verdict, which is the fault-that-reports-like-success
    # the individual writers refuse. The window is real: a `turn` probe runs for
    # minutes, and discovery pruning this connection's intersect row inside that
    # window leaves the second UPDATE matching no row.
    #
    # This is why the writers take `conn`: they join the transaction opened here
    # instead of acquiring their own connection, so a refusal from either one rolls
    # back both.
    async with pool.acquire() as conn:
        async with conn.transaction():
            capability = await record_capability(
                pool, model_id, test_id, outcome, duration_ms, tested_by, evidence,
                conn=conn,
            )
            performance = await record_performance(
                pool, connection_id, model_id, test_id, duration_ms, outcome,
                conn=conn,
            )
    return capability, performance
