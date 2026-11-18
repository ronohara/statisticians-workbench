-- Drop the per-test results column from ProviderModel.
--
-- This undoes 0013, from the abandoned AI-model-suitability plan. That plan put a
-- result on one row per provider and model, keyed by (providerCode, modelName), and
-- the key cannot tell two servers apart when they share a provider code: a refresh
-- through one Ollama host deleted another host's models and the results recorded
-- against them. The design that replaces it — workbench-AI-models-testing-design-v2
-- — records capability on the model and performance on the connection, in tables
-- this one does not touch.
--
-- So the column goes, and with it the six results it holds. That is intended: they
-- are development data produced by a design that is being replaced, and they cannot
-- be resolved into the new shape because they do not record which connection
-- produced them.
--
-- THE ROWS STAY
-- The 426 ProviderModel rows are the provider's catalogue and the admin page reads
-- them. The new tables are populated from the live servers by discovery, and until
-- that runs those rows are the only model list the application has.
--
-- ONE CHAIN, NOT TWO
-- The deployment chain never received this column: sawhorse/migrations/00005 was
-- written for packaging and no package has been cut since, so that file is deleted
-- rather than reversed. A chain that has run is history; this one has run nowhere.
--
-- The constraint drops with the column; naming it first would be redundant, but it
-- is named anyway so the statement reads correctly if someone runs it twice.
ALTER TABLE public."ProviderModel"
    DROP CONSTRAINT IF EXISTS "ProviderModel_testResults_object_check";

ALTER TABLE public."ProviderModel"
    DROP COLUMN IF EXISTS "testResults";
