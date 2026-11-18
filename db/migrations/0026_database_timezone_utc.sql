-- Every database this application owns defaults to UTC, so a psql session reads the same
-- timestamp on every machine.
--
-- Plan: workbench-documents/workbench-timestamp-schema-plan.html, Item 12 (Stage 4).
-- The Go deployed chain carries the same statements as
-- workbench-go/sawhorse/migrations/00016_database_timezone_utc.sql.
--
-- WHY A MIGRATION AND NOT A HAND-RUN ALTER
--
-- The application pins its own connections to UTC (`_init_connection` in Python,
-- `db.PinSessionUTC` in Go), so the application is unaffected either way. What a
-- database-level default changes is everything *outside* the pools: a psql session, an
-- operator's migration, the packaging pipeline's importer. Setting that by hand on one
-- machine leaves dev and a deployment with different defaults and no record of the
-- difference — which is exactly the drift this migration removes. A database default is
-- schema-level configuration, so it belongs in the schema chain.
--
-- WHY THE CURRENT DATABASE IS NAMED DYNAMICALLY
--
-- The deployment database is not called `workbench`; `sawhorse` creates it from the
-- installer's configuration (`cfg.Name`), so a literal name here would silently alter
-- nothing on a customer's machine — or fail. `current_database()` is the only name that
-- is right on both.
--
-- WHAT THIS DOES NOT COVER, AND WHY THE CODE CHANGED TOO
--
-- `workbench_data` is created at RUNTIME, not by this chain: the installer runs these
-- migrations against an empty `workbench`, and `workbench_data` appears on the first
-- start (`EnsureDataDatabase` in Go, `ensure_data_database` in Python). So on a fresh
-- install it does not exist when this migration runs, and the conditional below is a
-- no-op there.
--
-- Two changes close that, and both are needed:
--   - this migration alters `workbench_data` **if it already exists**, which is what
--     fixes an installation that was set up before this migration;
--   - both creation paths now set the zone on the database they create, which is what
--     covers a fresh install.
--
-- A migration alone cannot do the second: it would have to create the database, and
-- creating it is the application's job, not the schema chain's.
--
-- WHAT THIS DOES NOT TOUCH
--
-- The cluster's own default (`ALTER SYSTEM SET timezone`) and `log_timezone`. Those are
-- server configuration, not schema, and a database-level setting overrides the first for
-- every connection to these databases. The consequence is stated rather than hidden:
-- a database created *outside* the application — one somebody makes by hand — still
-- inherits the cluster default, and PostgreSQL's own log lines follow `log_timezone`.

DO $$
BEGIN
    -- The database this migration is running in. Right on a deployment whose database
    -- is named something else, which a literal would not be.
    EXECUTE format('ALTER DATABASE %I SET timezone = %L', current_database(), 'UTC');

    -- The data database, when it already exists. Absent on a fresh install, where the
    -- creation paths below take over — see the header.
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'workbench_data') THEN
        EXECUTE format('ALTER DATABASE %I SET timezone = %L', 'workbench_data', 'UTC');
    END IF;
END
$$;
