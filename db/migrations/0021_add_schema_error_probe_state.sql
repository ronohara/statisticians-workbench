-- A seventh probe state: connected, but reading the schema failed.
--
-- The Go deployed chain carries the same change as sawhorse/migrations/00011_add_schema_error_probe_state.sql.
-- This file is the development chain: it is the copy the dev database is migrated with.
--
-- WHY A SEVENTH STATE AND NOT A MESSAGE RULE
-- `Access Northwind` (connections 144 and 274) reported:
--
--   ERROR: msaccess: column "Attachments" of table "Employees" has DAO type 101
--          (Unknown), which the type map does not place (SQLSTATE XX000)
--
-- and the classifier put it in `unreachable`, because that is the fallback for an
-- unrecognised message. The fallback is the safe direction for a refusal and it is
-- still wrong here: the host answered, the mount was live, and the endpoint
-- returned an error about the CONTENT of one table. `unreachable` tells the model
-- to try another connection, which sends a user to check a network that is fine.
--
-- Adding "msaccess" to the message rules would catch this one vendor's phrasing
-- and nothing else. The probe already knows the distinguishing fact without
-- reading the message at all: the CONNECT SUCCEEDED. A failure after that point
-- cannot be unreachability.
--
-- WHY probeSuccessAt IS NOT RELAXED
-- Its constraint allows a success timestamp only when the state is 'reachable',
-- and that stays correct. The column answers "when was this last usable", and a
-- connection whose schema cannot be read is not usable. Admitting schema_error
-- would make the answer mean "did the socket open", which is not what a user
-- asking "has this ever worked" wants to know.

ALTER TABLE public."UserDatabaseConnection"
    DROP CONSTRAINT IF EXISTS "UserDatabaseConnection_probeState_known";

ALTER TABLE public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_probeState_known"
    CHECK ("probeState" IS NULL OR "probeState" IN
           ('reachable', 'unreachable', 'auth_failed', 'no_database',
            'no_permission', 'incomplete', 'schema_error'));

-- ============================================================
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
-- ============================================================
--
-- No backfill. The six existing states are unaffected, and a row already holding
-- 'unreachable' that should be 'schema_error' will be corrected by its next probe
-- — which is what the 60-second TTL exists for. A backfill would have to re-probe
-- every connection during a migration, which is not a migration's job.
--
-- No new column. The phase that produces this state is known during the probe and
-- is not persisted: it is a fact about one attempt, not about the connection.
