-- The three columns that already held UTC become timestamptz, which is the type
-- that says so.
--
-- Plan: workbench-documents/workbench-timestamp-schema-plan.html, Item 4 and Item 4a.
-- Design: workbench-timestamp-schema-design.html. Evidence: the sweep report.
-- The Go deployed chain carries the same statements as
-- workbench-go/sawhorse/migrations/00013_timestamptz_utc_columns.sql.
--
-- NO ZONE CLAUSE, AND THAT IS THE POINT
--
-- This migration shipped with `USING "probedAt" AT TIME ZONE 'UTC'` on each column,
-- which was correct when it was written and is now a violation of the rule the design
-- settled on 2026-11-08: **never put a timezone in the database.** Not in a column
-- type, not in a DEFAULT, not in a USING clause.
--
-- The reason is that this file ships to every installation. A zone name in it is a
-- statement about the machine that wrote the file — and nothing pins a deployment's
-- cluster zone: the Windows installer's initdb passes no --timezone, and no file in
-- workbench-linux or workbench-go/sawhorse sets one. `'UTC'` is the least harmful
-- name to hardcode, but the rule is structural rather than a judgement about which
-- name is tolerable, because an exception that reads "UTC is fine" is the exception
-- somebody later extends to a zone that is not.
--
-- WHAT REMOVING IT CHANGES, MEASURED
--
-- On populated naive data the two forms differ, by exactly the session offset:
--
--   USING t AT TIME ZONE 'UTC'   '2026-11-07 02:30:13' -> 2026-11-07 09:30:13+07
--   no USING clause              '2026-11-07 02:30:13' -> 2026-11-07 02:30:13+07
--
-- That difference is why the edit is safe, and it is not hand-waving:
--
--   - On a fresh install these tables are EMPTY when this runs. The baseline is a
--     schema dump with no INSERT and no COPY, and no migration before this one writes
--     a row into either table. So there is no value to reinterpret and the two forms
--     are identical in effect.
--   - On this development database the conversion has already run, so editing the
--     file changes nothing that has executed.
--   - The rows that exist here are history, and history is discarded (D5). Their
--     zone is not recorded anywhere, so there is nothing to preserve and nothing a
--     clause could assert truthfully.
--
-- WHAT THIS MIGRATION DOES NOT DO
--
-- No data correction and no index work. The probe columns carry CHECK constraints
-- that reference them; PostgreSQL re-verifies a constraint against the rewritten
-- table during ALTER TYPE, so a row that violated one would fail the migration
-- rather than survive it silently.
--
-- AND THE WRITERS HAD TO CHANGE IN THE SAME BREATH
--
-- Measured 2026-11-08 on this database: `pg_typeof(now() AT TIME ZONE 'UTC')` is
-- `timestamp without time zone`, and assigning that to a `timestamptz` column
-- reinterprets it in the session zone — a measured seven hours early. So the three
-- writers that wrapped `NOW()` in that expression were simplified to plain `NOW()` in
-- the same change. Left as they were, this migration would have converted the history
-- and then corrupted every value written afterwards. That expression is what Item 13
-- sweeps for, and it must now appear in tests and Down migrations only.

ALTER TABLE public."UserDatabaseConnection"
    ALTER COLUMN "probedAt"       TYPE timestamptz,
    ALTER COLUMN "probeSuccessAt" TYPE timestamptz;

ALTER TABLE public."UserDataset"
    ALTER COLUMN "materializedAt" TYPE timestamptz;
