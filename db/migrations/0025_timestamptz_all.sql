-- Every remaining naive timestamp column becomes timestamptz, with no zone clause.
--
-- Plan: workbench-documents/workbench-timestamp-schema-plan.html, Item 7 (Stage 3).
-- Design: workbench-timestamp-schema-design.html. The Go deployed chain carries the same
-- statements as workbench-go/sawhorse/migrations/00015_timestamptz_all.sql.
--
-- WHAT CHANGES
--
-- 66 columns on 30 tables, measured from the catalogue rather than transcribed:
--
--   SELECT table_name, column_name FROM information_schema.columns
--    WHERE table_schema = 'public'
--      AND data_type = 'timestamp without time zone'
--    ORDER BY table_name, column_name;
--
-- The list below IS that query's output on 2026-11-08. A column added between writing
-- this and running it would not be in it, which is why the verification for this item
-- counts the catalogue afterwards instead of trusting this file: the query is the
-- authority, and the file is a transcript of it.
--
-- NO ZONE CLAUSE, AND NO ZONE NAME
--
-- Each column converts with a bare `TYPE timestamptz`. The implicit cast reinterprets
-- the stored value in the session's zone, and those values are discarded — this is a
-- development system with no production deployments, so there is no history to keep
-- (D5), and a zone name in a shipped migration is a fact about one machine (D6).
-- Together those two decisions are why this is one statement per table instead of a
-- cohort per column group with its own declared zone.
--
-- WHAT THIS MIGRATION DOES NOT FIX
--
-- The type. Not the writers: a Python `datetime.utcnow()` is a naive value, and bound
-- to a timestamptz column it is interpreted in the session zone — measured 25,200
-- seconds from the correct instant. Item 7a converts those sites, and it is the half
-- that makes this migration hold. Applied alone, this file would convert the history
-- correctly and then let every subsequent write land seven hours early.
--
-- Nor the readers: password_reset.py and email_verification.py compare a stored value
-- against a naive clock, which raises TypeError once the column is aware rather than
-- silently misjudging. That is Item 11a, and raising is the good outcome.
--
-- CONSTRAINTS
--
-- PostgreSQL re-verifies every CHECK on a rewritten table, not only the ones that
-- reference a converted column, so a constraint that no longer holds fails the
-- migration rather than surviving it.
--
-- Checked before writing this, by listing every CHECK on every table that carries a
-- naive timestamp: 17 constraints. Fifteen of them constrain tuning numbers, an
-- enum-like text column, a jsonb type or a single-row rule, and none of those touches a
-- timestamp. The other two are the probe's, on `UserDatabaseConnection`:
-- `probe_timestamped` and `probeSuccessAt_needs_probe`. They do compare timestamps — but
-- against each other, on two columns that Item 4 already converted to `timestamptz`, and
-- both hold (0 violations measured). They are re-verified when this migration rewrites
-- that table for its `createdAt` and `updatedAt`, and they hold there too.
--
-- INDEXES AND REWRITES
--
-- ALTER TYPE rewrites each table and rebuilds its indexes. At this size that is fine;
-- it is a full pass per table, not a metadata change, and the 30 statements run in one
-- transaction so a failure leaves no table half-converted.

ALTER TABLE public."AIProvider"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."AIRecipeSession"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."Account"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."Chat"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."ConnectionModelIntersect"
    ALTER COLUMN "lastSeenAt" TYPE timestamptz;

ALTER TABLE public."DataCleanChat"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."DataCleanupManifest"
    ALTER COLUMN "createdAt" TYPE timestamptz;

ALTER TABLE public."DataPreparationRule"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."DatasetDescription"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "generatedAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."GlobalSettings"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."LLMModel"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."Message"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."NotebookImport"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "importedAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."PasswordResetToken"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "expiresAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."ProviderModelIntersect"
    ALTER COLUMN "firstSeenAt" TYPE timestamptz;

ALTER TABLE public."Recipe"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."RecipeExecution"
    ALTER COLUMN "completedAt" TYPE timestamptz,
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "startedAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."RecipePreparationRule"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."Session"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "expires" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."Translation"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."User"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "deletedAt" TYPE timestamptz,
    ALTER COLUMN "emailVerified" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."UserAIConnection"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."UserDatabaseConnection"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."UserDataset"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."UserGroup"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."VerificationToken"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "expiresAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."VirtualDatasetChat"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."VisualizationInstance"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."VisualizationType"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;

ALTER TABLE public."user_audio_presets"
    ALTER COLUMN "createdAt" TYPE timestamptz,
    ALTER COLUMN "updatedAt" TYPE timestamptz;
