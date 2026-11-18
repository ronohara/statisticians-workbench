-- Let a connection record that it has stopped working, after it has worked.
--
-- The Go deployed chain carries the same statements as
-- workbench-go/sawhorse/migrations/00014_probe_success_history.sql.
--
-- THE BUG THIS FIXES
--
-- A probe of a connection that had previously succeeded could not be recorded at
-- all. Measured 2026-11-08, connection 3:
--
--   could not record probe for connection 3: new row for relation
--   "UserDatabaseConnection" violates check constraint
--   "UserDatabaseConnection_probeSuccessAt_reachable"
--
-- The UPDATE set `probeState` to the new value and, on a failure, kept the existing
-- `probeSuccessAt` via `CASE WHEN $4 THEN NOW() ELSE "probeSuccessAt" END`. A row that
-- had ever succeeded therefore carried a non-null stamp while the new state was
-- `unreachable`, which the old constraint forbade. PostgreSQL rejected the whole
-- statement, the handler logged a WARNING and continued, and the row kept its previous
-- state — including the old `probedAt`.
--
-- What a user saw: the API answered `unreachable` while the table still read
-- `reachable` with a timestamp hours old, so the panel showed a working connection
-- that had simply not been checked in a while. Because `probedAt` never advanced,
-- `probe_is_fresh` reported the answer stale and every sweep retried and failed the
-- same way.
--
-- WHY THE OLD CONSTRAINT WAS WRONG, STATED AS THE MEANINGS
--
-- The product asks one column for one meaning — "when did this last succeed" — and the
-- old constraint asked it for a second: "when did the current state begin". Those are
-- the same instant only while the connection is reachable, because reachability is
-- established by a success. They diverge at the first failure: last worked 10:00, broken
-- since 12:00. A constraint permitting a value only in the state where the two agree
-- does not resolve the collision, it encodes it, and it makes the transition the panel
-- exists to report unrepresentable.
--
-- Three requirements, and none of them asks "when did this state begin":
--   has this ever been tested   ->  probedAt IS NOT NULL
--   what is the latest status   ->  probeState + probeDetail, paired with probedAt
--   when was the last success   ->  probeSuccessAt
--
-- So `probeSuccessAt` is an event ("when it last worked"), not a status. It advances on
-- success and is untouched by anything else. `probeState` and `probedAt` already answer
-- the other two, and `probe_timestamped` already keeps them paired.
--
-- WHAT THIS MIGRATION DOES NOT DO
--
-- No new column. An earlier draft added `probeStateSince` for "when this state began";
-- restating the requirements showed nothing asks for it, so it was dropped rather than
-- built. No data correction either: 0 rows currently carry a success stamp with a
-- non-reachable state, because the old constraint has been preventing the transition
-- rather than leaving bad data behind.
--
-- No writer or reader change in either backend. The statement has always written what
-- it should; the constraint was refusing it.

ALTER TABLE public."UserDatabaseConnection"
    DROP CONSTRAINT IF EXISTS "UserDatabaseConnection_probeSuccessAt_reachable";

-- The replacement asserts what is actually true of the value, and both clauses earn
-- their place:
--
--   probedAt IS NOT NULL   A success stamp cannot exist without a probe having run.
--                          Written explicitly because a CHECK passes when the
--                          expression is NULL, and `probeSuccessAt <= probedAt` is
--                          NULL when probedAt is NULL — an implicit guard would let a
--                          stamp exist with no probe at all.
--
--   <= probedAt            A success cannot be later than the last probe. It is set to
--                          NOW() in the same statement that sets probedAt, and kept
--                          thereafter, so it is equal at the moment of success and
--                          earlier afterwards.
--
-- Verified against the data before writing this: 0 rows have probeSuccessAt > probedAt,
-- 0 have a stamp with probedAt NULL, and the 8 rows that have a stamp have it equal to
-- probedAt — the set-together case.
ALTER TABLE public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_probeSuccessAt_needs_probe"
    CHECK ("probeSuccessAt" IS NULL
           OR ("probedAt" IS NOT NULL AND "probeSuccessAt" <= "probedAt"));

-- The old name told the wrong story: `..._reachable` states that a success stamp implies
-- the connection is reachable, which is the meaning this migration removes. A constraint
-- whose name lies is how the next reader talks themselves into "fixing" the writer back
-- to match it.
