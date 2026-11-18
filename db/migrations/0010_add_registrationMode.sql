-- Add the registrationMode column to GlobalSettings (registration options plan).
-- Mirrors the sawhorse migration 00002_registration_mode.sql so the Python dev
-- database gains the column when migrated independently of sawhorse.
-- 0 (default) self-register auto-verified; 1 admin-created; 2 self-register +
-- admin-verified; 4 self-register + email verification.
ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "registrationMode" integer NOT NULL DEFAULT 0;
