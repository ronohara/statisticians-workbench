-- CreateTable: DataCleanupManifest — what a deleted account still owns in workbench_data.
-- Mirrors the sawhorse migration 00004_add_data_cleanup_manifest.sql so the Python dev
-- database gains the table when migrated independently of sawhorse.
--
-- One row per object the account owns in the data database and that has to be dropped with
-- it. The account delete and the object drop cannot share a transaction — they are two
-- databases — so these rows, written before the delete, are what make the drop retryable
-- afterwards, and what a reconciliation sweep finishes if the process dies in between.
--
-- Deliberately NO foreign key to "User", unlike every other user-owned table in this schema:
-- the row has to outlive the very delete it describes, and a foreign key to "User" would be
-- cascaded away with the account, taking the retry with it. This is the one exception, and it
-- is deliberate rather than forgotten.
--
-- "objectKind" is open text with no CHECK, also on purpose: a kind a constraint did not know
-- would be rejected at exactly the moment a cleanup record must be written, and a missing
-- record is an orphaned object. The drop is built from the kind as
--     user_schema, notebook_schema  →  DROP SCHEMA IF EXISTS "…" CASCADE
--     upload, clean, virtual        →  DROP TABLE  IF EXISTS public."…"
CREATE TABLE public."DataCleanupManifest" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "userId" text NOT NULL,
    "objectKind" text NOT NULL,
    "objectName" text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT "DataCleanupManifest_pkey" PRIMARY KEY (id)
);

CREATE INDEX "DataCleanupManifest_userId_idx" ON public."DataCleanupManifest" USING btree ("userId");
