-- Two columns that make "materialise this dataset" a decision with a state.
--
-- The Go deployed chain carries the same change as sawhorse/migrations/00012_add_materialize_state.sql.
-- This file is the development chain: it is the copy the dev database is migrated with.
--
-- WHY TWO COLUMNS AND NOT A SECOND BOOLEAN
--
-- `materialized` already exists and records the user's CHOICE. What it could not
-- express is whether the choice had been carried out. Measured 2026-11-06: the
-- manual editor's switch wrote the flag and nothing acted on it — the only
-- consumer was the dataset delete, deciding whether to drop a table. A dataset
-- defined as materialised had no table, and no way to say so.
--
-- "Done" as a boolean would lie in exactly the case that matters. Build a table
-- from definition A, edit the joins to B, attempt a rebuild that fails: the table
-- exists but matches a definition the dataset no longer holds. `true` reports a
-- fault as success. A TIMESTAMP cannot: it is cleared whenever the definition
-- changes, so a non-null `materializedAt` means "current for the definition now
-- stored", and it can only ever be true.
--
-- WHY THE ERROR IS STORED
--
-- Save-and-report means the definition is written and the build attempted after.
-- The failure has to outlive the response so a user who returns the next day can
-- see that the table was never built and retry it. A message that exists only in
-- the moment of saving is invisible by the next morning.
--
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
--
-- No backfill. Every existing row carrying `materialized = true` has no table —
-- nothing ever built one — so `materializedAt` stays NULL for all of them, which
-- is the truth. A backfill would have to run every join during a migration, which
-- is not a migration's job; the retry endpoint exists for that, per dataset, at
-- the user's choosing.

ALTER TABLE public."UserDataset"
    ADD COLUMN IF NOT EXISTS "materializedAt"   timestamp without time zone,
    ADD COLUMN IF NOT EXISTS "materializeError" text;

-- An error about a table nobody asked for is incoherent: if there is a
-- materialisation error, the dataset is a materialised one.
ALTER TABLE public."UserDataset"
    DROP CONSTRAINT IF EXISTS "UserDataset_materializeError_implies_choice";

ALTER TABLE public."UserDataset"
    ADD CONSTRAINT "UserDataset_materializeError_implies_choice"
    CHECK ("materializeError" IS NULL OR "materialized");

-- The console needs to find the datasets whose table is missing or out of date
-- without scanning every row, because that is the query behind the badge.
CREATE INDEX IF NOT EXISTS "UserDataset_materialize_attention"
    ON public."UserDataset" ("userId")
    WHERE "materialized" AND "materializedAt" IS NULL;
