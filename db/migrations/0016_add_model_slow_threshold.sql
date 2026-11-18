-- The model-slow threshold: two columns, one judgement.
--
-- Plan: workbench-AI-models-testing-plan-v2.html, Item 21.
-- Mirrors sawhorse/migrations/00006_add_model_slow_threshold.sql so the Python dev
-- database gains the columns when migrated independently of sawhorse.
--
-- WHY THIS IS 0016 AND NOT AN EDIT OF 0015
-- 0015 is applied and committed. A column added to it now would not reach a database
-- that has already run it, so two databases would both claim to have run 0015 and hold
-- different schemas. A new file is the only way to add a column to an applied chain.
--
-- WHAT "TOO SLOW" IS
-- Not a property of a model and not a property of a server. It is a judgement, and it
-- belongs to the person waiting: the same 41 s measurement is fine for a lunch break and
-- unusable in a chat window. So the threshold is per user, inherited from a global
-- default, and the comparison happens at READ time — a stored duration is compared
-- against the user's current limit whenever it is read, so raising the limit unblocks
-- past results without re-testing.
--
-- NULL MEANS "NO VALUE OF MY OWN", NOT "ZERO"
-- Both columns are nullable, and NULL is the only sentinel used. The existing upload
-- settings use 0 for "inherit", but register.py copies those defaults into the user row
-- at registration, so inheritance is decided once and never moves. This setting must
-- resolve live — changing the global default has to move every user who has no value of
-- their own, and no user who has one. A copy would freeze it, and 0 would collide with
-- a legitimate "no limit".
--
-- NO GROUP LEVEL
-- The design settles it: groups govern connection sharing, they do not govern patience.
-- A third level would be a third place to reason about for a setting that is, in the
-- end, one number.

ALTER TABLE public."User"
    ADD COLUMN IF NOT EXISTS "modelSlowThresholdSeconds" integer;

-- NOT NULL with a DEFAULT, because this tier must never be absent.
--
-- A nullable global would mean the real value lives in code as a fallback, which is the
-- hidden default the project's No Silent Enhancement rule forbids: the admin's field would
-- be empty, the number in force would be invisible, and nulling the column would silently
-- reinstate it. Making the value data means there is one authority — the row — and the
-- constant below is only the seed that creates it.
--
-- 30 seconds, and the reason is the design's own worked example ("took 41.2 s, your limit
-- is 30 s"), so the number a reader meets in the design is the number the database holds.
-- A shorter limit refuses models a local GPU answers in 12 s; a much longer one delivers
-- the refusal after the user has given up waiting, which is the situation it exists to
-- prevent.
ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "defaultModelTestSeconds" integer NOT NULL DEFAULT 30;

-- The resolution is a COALESCE over two columns, with no third tier:
--     COALESCE(user.modelSlowThresholdSeconds, global."defaultModelTestSeconds")
-- The global column is NOT NULL, so there is nothing for a code constant to answer — the
-- constant in user_settings.py is the seed for a new row, not an arbiter. A third tier in
-- code would be an unseen number competing with a visible one.
--
-- A negative value is refused by the API rather than by a CHECK constraint: the same
-- refusal must produce the same translated message in both backends, and a constraint
-- violation cannot carry one.

-- ============================================================
-- GlobalSettings IS A SINGLETON, AND NOW SAYS SO
-- ============================================================
--
-- The table has always been a singleton by convention: id defaults to 1, the primary key
-- stops duplicate ids, and every reader in the tree pins WHERE id = 1. What the schema
-- did NOT stop was id = 2. Three consequences, in order of how easy they are to notice:
--
--   1. It would be written and never read. Eight call sites pin id = 1 — email.py,
--      password_reset.py twice, email_verification.py, register.py, admin/users.py twice,
--      admin/global_settings.py — so a second row is an authoritative-looking
--      configuration that no code consults.
--   2. Nothing would report it. There is no query that counts rows, so the divergence
--      between what an operator believes is configured and what the code reads is silent.
--   3. It cannot be detected after the fact without knowing to look.
--
-- Silent unread data is harder to notice than an outage, which is why the rule belongs in
-- the schema rather than in a convention. With this constraint the PK keeps the unique
-- index and the CHECK excludes every other id, so "exactly one row" is structural and
-- every WHERE id = 1 becomes a statement about the only row there is.
--
-- NOT a NOT NULL singleton-by-pseudo-key alternative (a single-column table with a
-- boolean PK): that would be a larger change to a table eight modules read, and this
-- achieves the same guarantee without touching a column they use.
ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_single_row" CHECK (id = 1);
