-- Add the per-test results column to ProviderModel.
--
-- The development chain. This repository's schema moves ahead of what any released
-- package carries: a change is written and applied here first, and the matching
-- sawhorse migration is written at the same time so that a package can be cut at any
-- moment without anyone having to reconstruct what changed since the last one.
--
-- WHAT THE COLUMN HOLDS
-- One jsonb object per model, keyed by test id ("tools", "competence", "turn", and
-- whatever is added later). Each value is written by
-- backend/src/routers/user/model_suitability.py as
--     { state, testedAt, testedBy, reason, evidence }
-- where state is one of "unknown", "pass", "fail".
--
-- NULL means no test has ever been run for this model; a MISSING KEY means that one
-- test has not been run. Three states are stored per key -- "unknown", "pass",
-- "fail" -- so a key present with state "unknown" says a result no longer stands,
-- while a missing key says nothing was ever recorded. Those are different facts and
-- the column keeps them apart.
--
-- WHY jsonb AND NOT A COLUMN PER TEST
-- The test set is expected to grow. A new test must cost a registry entry
-- (backend/src/chat/test_registry.py) rather than a migration in two chains and a
-- change to two backends' scan code.
--
-- WHY THE INNER STATES ARE NOT CONSTRAINED
-- jsonb cannot express "every value's state is one of three strings" without a
-- trigger, and a trigger would put the rule in the database while the row is written
-- by one function that already validates it — and that function also refuses an
-- unregistered test id, which no constraint here could know about.
--
-- What the database can cheaply enforce is the top-level shape, and does: an array, a
-- string or a number is refused, so the column cannot be filled with something every
-- reader would then have to defend against.
ALTER TABLE public."ProviderModel"
    ADD COLUMN IF NOT EXISTS "testResults" jsonb;

ALTER TABLE public."ProviderModel"
    DROP CONSTRAINT IF EXISTS "ProviderModel_testResults_object_check";

ALTER TABLE public."ProviderModel"
    ADD CONSTRAINT "ProviderModel_testResults_object_check"
    CHECK ("testResults" IS NULL OR jsonb_typeof("testResults") = 'object');
