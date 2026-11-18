-- Connection probe state: can this database connection be reached, and if not, why?
--
-- The Go deployed chain carries the same change as sawhorse/migrations/00010_add_connection_probe_state.sql.
-- This file is the development chain: it is the copy the dev database is migrated with.
--
-- WHY THE CONNECTION ROW AND NOT A SEPARATE TABLE
-- Reachability is a property of the connection: shared by every session, every user and
-- the tree. A small state table would hold the same four fields and force every reader to
-- LEFT JOIN it, with a missing row meaning "never probed" — a distinction a nullable
-- column on the row already makes, without the join. The house precedent for observation
-- state is keyed-and-overwritten (ConnectionModelIntersect."connectionTestResults"), not a
-- log. History was considered and declined: it is a diagnostic record with its own
-- retention rules, and it would couple read latency to table growth.
--
-- WHY NULLABLE AND NOT DEFAULTED
-- NULL means "never probed", which is not "reachable" and not "unreachable". A default
-- would make every existing row claim a probe it never had, and the reader could not tell
-- an untested connection from a tested one. No backfill, for the same reason 00008 gives:
-- freezing a default into every row makes a later change silently ineffective.
--
-- WHY probeSuccessAt IS SEPARATE FROM probedAt
-- "Has this ever worked" is a different question from "when was it last looked at", and it
-- is the one a user asks when a connection that used to work now fails. One extra column
-- answers it without a counter or a log.

ALTER TABLE public."UserDatabaseConnection"
    ADD COLUMN IF NOT EXISTS "probeState" text;

ALTER TABLE public."UserDatabaseConnection"
    ADD COLUMN IF NOT EXISTS "probeDetail" text;

ALTER TABLE public."UserDatabaseConnection"
    ADD COLUMN IF NOT EXISTS "probedAt" timestamp;

ALTER TABLE public."UserDatabaseConnection"
    ADD COLUMN IF NOT EXISTS "probeSuccessAt" timestamp;

-- ============================================================
-- THE STATES, AND WHY THE LIST IS CLOSED
-- ============================================================
--
-- A CHECK rather than free text, because each state implies a different next move for the
-- model and for the user, and an unexpected string would silently mean "unknown behaviour":
--
--   reachable      connected, schema readable
--   unreachable    DNS, refused, timed out — try another connection
--   auth_failed    bad user or password — do not retry; the credential needs fixing
--   no_database    the host answered and the database is not there — try another connection
--   no_permission  connected, but the schema is not readable by this account — retry is
--                  pointless
--   incomplete     the connection row itself is missing host, port or database — a data
--                  fault, and reporting it as "unreachable" would send someone to check a
--                  network that is fine
--
-- NULL is not in the list: it means never probed, which is the absence of a state.
--
-- The constraint is a backstop, not the refusal a user sees. The probe classifies from the
-- driver message, and a class it does not recognise arrives as `unreachable` with the raw
-- message in probeDetail — the honest report for a failure whose reason is unknown.
ALTER TABLE public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_probeState_known"
    CHECK ("probeState" IS NULL OR "probeState" IN
           ('reachable', 'unreachable', 'auth_failed', 'no_database', 'no_permission', 'incomplete'));

-- A state with no timestamp would be a claim with no age, and the reader's freshness rule
-- depends on the age. Either both are written or neither is.
ALTER TABLE public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_probe_timestamped"
    CHECK (("probeState" IS NULL) = ("probedAt" IS NULL));

-- A success timestamp on a row that has never succeeded is a contradiction. The probe sets
-- probeSuccessAt only when the state is `reachable`.
ALTER TABLE public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_probeSuccessAt_reachable"
    CHECK ("probeSuccessAt" IS NULL OR "probeState" = 'reachable');

-- ============================================================
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
-- ============================================================
--
-- No index. The columns are read by primary key on a row the caller already has, from a
-- listing that returns every connection the user can see.
--
-- No TTL column. Freshness is a read rule — `probedAt > now() - 60s` — not a stored
-- setting, because a stale negative must degrade to "unknown" rather than stay a claim.
-- Putting the TTL in the row would make it per-connection, which nobody asked for, and
-- would put the number in the schema rather than in the code that applies it.
--
-- No probe history. See the header: declined deliberately, and it can be added later as a
-- log with its own retention without touching these columns.
