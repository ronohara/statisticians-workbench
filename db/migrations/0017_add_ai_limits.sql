-- AI limits: three tuning values, on the pair the user already chooses.
--
-- Plan: workbench-ai-limits-plan.html, Item 1.
-- Mirrors sawhorse/migrations/00007_add_ai_limits.sql so the Python dev database
-- gains the columns when migrated independently of sawhorse.
--
-- WHY THREE VALUES AND NOT ONE
-- A single global timeout cannot serve both a local CPU model and a cloud API. The
-- describe workload was measured at 345 s on deepseek-r1:8b, while an
-- OpenAI-compatible endpoint wants tens of seconds; any one number is wrong for one
-- of them. Temperature has the same shape — a reasoning model may want determinism
-- where a small local model needs creativity to produce anything interesting.
--
-- WHY ON THE PAIR, AND NOT PER USER
-- Every AI request already carries (connectionId, model) explicitly: chat_router.py
-- passes both into send_message, describe.py passes both into create_llm. Tuning
-- stored on that pair sits exactly where the choice is made. It is also not an
-- allotment — nothing accumulates — so a per-user column would create a field that
-- may never vary, which is the UserAIConnection.defaultModel failure mode.
--
-- The same value applies to every interface. Setting it in chat also applies in
-- describe, because it is the same model on the same connection: one behaviour per
-- model rather than one per screen.
--
-- NULL MEANS "INHERIT", NOT "ZERO"
-- A temperature of 0 is meaningful and must survive as a value; a timeout of 0 and a
-- token cap of 0 are not. These columns are nullable precisely so the resolver can
-- tell "not configured" from "configured to the smallest legal value". A
-- NOT NULL DEFAULT 0 on any of them would destroy that distinction.

-- double precision, not numeric, for two reasons. The tree already uses it for its
-- float tunables (user_audio_presets.micVolume, pitch, speed, volume), so this follows
-- the established convention rather than introducing a second one. And a numeric column
-- comes back as Decimal in Python and pgtype.Numeric in Go, neither of which serialises
-- into a provider payload without a conversion step at every call site — for a value
-- whose job is to be handed straight to an API, float is the honest type.
ALTER TABLE public."ConnectionModelIntersect"
    ADD COLUMN IF NOT EXISTS "temperature" double precision;

ALTER TABLE public."ConnectionModelIntersect"
    ADD COLUMN IF NOT EXISTS "maxTokens" integer;

ALTER TABLE public."ConnectionModelIntersect"
    ADD COLUMN IF NOT EXISTS "timeoutSeconds" integer;

-- The workbench-wide defaults, on the settings row that already exists.
--
-- NOT NULL with a DEFAULT, for the reason 0016 gives for defaultModelTestSeconds: a
-- nullable global would put the real value in code as a fallback, which is the hidden
-- default the No Silent Enhancement rule forbids. Making it data means there is one
-- authority — the row — and the constants in llm_connection.py and connection.go are
-- the seed for a new row, not an arbiter of what is in force.
--
-- 0.7 and 4000 are the values the code has carried since the feature was written, so
-- nobody's behaviour changes on migration. 120 s is new: it sits above the provider
-- defaults it replaces (Python 300 s for chat, Go 60 s) for a paid endpoint and below
-- the 345 s the local model needs, which is the point — a pair that needs longer is
-- tuned on the pair, not by raising the ceiling for everyone.
ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "temperature" double precision NOT NULL DEFAULT 0.7;

ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "maxTokens" integer NOT NULL DEFAULT 4000;

ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "timeoutSeconds" integer NOT NULL DEFAULT 120;

-- ============================================================
-- RANGE CHECKS: A BACKSTOP, NOT THE REFUSAL THE USER SEES
-- ============================================================
--
-- 0016 refused a CHECK for negative values, and its reason still holds: a constraint
-- violation cannot carry a translated message, and the two backends must refuse the
-- same input with the same words. So the API validates first and produces the coded,
-- translated refusal; these constraints are what stops a write that bypasses the API —
-- a hand-run UPDATE, a future script, a seed file.
--
-- The distinction is which failure is expected. A bad value arriving through the API
-- is ordinary user error and gets a 400 with a message. A constraint firing means the
-- code wrote something it should have refused, which is a bug, and a 500 is the honest
-- answer for it.
--
-- The band is the provider contract, not a preference: OpenAI-compatible endpoints
-- accept 0 to 2. A value outside it is not "more of" anything — it is rejected
-- downstream or silently clamped, and either way the tuning the user set is not the
-- tuning in force.
ALTER TABLE public."ConnectionModelIntersect"
    ADD CONSTRAINT "ConnectionModelIntersect_temperature_range"
    CHECK ("temperature" IS NULL OR ("temperature" >= 0 AND "temperature" <= 2));

ALTER TABLE public."ConnectionModelIntersect"
    ADD CONSTRAINT "ConnectionModelIntersect_maxTokens_positive"
    CHECK ("maxTokens" IS NULL OR "maxTokens" > 0);

ALTER TABLE public."ConnectionModelIntersect"
    ADD CONSTRAINT "ConnectionModelIntersect_timeoutSeconds_positive"
    CHECK ("timeoutSeconds" IS NULL OR "timeoutSeconds" > 0);

ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_temperature_range"
    CHECK ("temperature" >= 0 AND "temperature" <= 2);

ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_maxTokens_positive"
    CHECK ("maxTokens" > 0);

ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_timeoutSeconds_positive"
    CHECK ("timeoutSeconds" > 0);

-- ============================================================
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
-- ============================================================
--
-- No backfill. Every existing row in ConnectionModelIntersect keeps NULL for all
-- three, which is what "nobody has tuned this pair" means, and the resolver falls
-- through to the global defaults — which are the values the code used before this
-- migration. So behaviour is unchanged for every existing pair, and unchanged for
-- every request, until someone tunes something.
--
-- No index. The resolver reads by primary key (connectionId, modelId), which already
-- exists; a tuning lookup is one row by its own key.
--
-- No trigger to maintain updatedAt on GlobalSettings. The backend sets NOW() on every
-- write, as it does for every other column in that table (project-design.md §1.4).
