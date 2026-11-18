-- Add the keyOrigin column to Translation (translation key-origin plan).
-- Mirrors the sawhorse migration 00003_translation_key_origin.sql so the Python
-- dev database gains the column when migrated independently of sawhorse.
-- Records which codebase a key originates from: F frontend (Next.js), P Python
-- backend, G Go backend, X not attributed (the default). text + CHECK rather
-- than an enum, so the permitted set is changed in one statement.
--
-- Attribution is not this file's job: the importers write the origin as they
-- import, and the snapshot step and debian/postinst carry it to installed
-- systems. Rows left at 'X' are rows nothing has attributed.
ALTER TABLE public."Translation"
    ADD COLUMN IF NOT EXISTS "keyOrigin" text NOT NULL DEFAULT 'X';

ALTER TABLE public."Translation"
    DROP CONSTRAINT IF EXISTS "Translation_keyOrigin_check";

ALTER TABLE public."Translation"
    ADD CONSTRAINT "Translation_keyOrigin_check"
    CHECK ("keyOrigin" IN ('F', 'P', 'G', 'X'));
