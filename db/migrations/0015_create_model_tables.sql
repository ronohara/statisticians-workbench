-- CreateTable: LLMModel — the model itself, independent of who serves it.
--
-- The development chain. Mirrors sawhorse/migrations/00005_create_llm_model.sql so
-- the Python dev database gains the table when migrated independently of sawhorse.
--
-- WHY THIS TABLE EXISTS AT ALL
-- The abandoned plan recorded a result on ProviderModel, keyed by
-- ("providerCode", "modelName"), and that key cannot tell two servers apart: a
-- refresh through one Ollama host deleted another host's models and the results
-- recorded against them. The design that replaces it — workbench-AI-models-testing-
-- design-v2 — separates three things that were being held in one row:
--
--   AIProvider          the driver (openrouter, ollama-local, deepseek)
--   UserAIConnection    one user's link to one server using that driver
--   LLMModel            the model itself, whoever serves it
--
-- This migration creates only the third. The two intersects that join it to a
-- provider and to a connection are Items 10 and 11 of
-- workbench-AI-models-testing-plan-v2.html, written next and deliberately not here:
-- one table per item keeps each row's acceptance checkable.
--
-- WHY modelName IS THE WHOLE IDENTITY
-- Two sightings are one model when their names match. No provider reliably exposes
-- a digest and hashing weights across three protocols is not a product feature, so
-- the name is the only practical key. The cost is accepted and recorded in the
-- design: a Q4 copy and a Q8 copy of the same model share one capability verdict.
-- The UNIQUE index is what makes it true under a race — two concurrent discoveries
-- cannot both insert one name, and the loser gets a constraint violation it must
-- handle rather than a second row nobody notices.
--
-- WHICH FACTS LIVE HERE, AND WHY
--   enabled, preferred, comment       the administrator's management choice. They
--                                     describe the model, not a server.
--   modelTestResults                  the three capability tests — tools,
--                                     competence, turn. A result obtained through
--                                     any connection is a result about the model.
--   (nothing about speed)             duration and the performance judgement are
--                                     facts about a server, and belong on
--                                     ConnectionModelIntersect. The same model
--                                     measured 4.6 s on one host and 189 s on
--                                     another is not a contradiction.
--
-- THE jsonb COLUMN IS THE ABANDONED ONE, REUSED VERBATIM IN SHAPE
-- Keyed by test id, one entry per test, missing key means that test has never run.
-- Its shape was right; the row underneath it was wrong. So the CHECK is the same
-- one 0013 added and 0014 dropped: an array, a string or a number is refused, which
-- stops the column holding something every reader would then have to defend against.
-- The inner states are deliberately not constrained — jsonb cannot express "every
-- value's state is one of three strings" without a trigger, and the single writer
-- already validates it, including the registered-test check no constraint could know.
--
-- "updatedAt" has a default but no trigger: the backend sets NOW() on every write,
-- and the default covers only the INSERT. That is the convention every other table
-- in this schema follows.
CREATE TABLE public."LLMModel" (
    id text DEFAULT gen_random_uuid() NOT NULL,
    "modelName" text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    preferred boolean DEFAULT false NOT NULL,
    comment text,
    "modelTestResults" jsonb,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT "LLMModel_pkey" PRIMARY KEY (id),
    CONSTRAINT "LLMModel_modelTestResults_object_check"
        CHECK ("modelTestResults" IS NULL OR jsonb_typeof("modelTestResults") = 'object')
);

CREATE UNIQUE INDEX "LLMModel_modelName_key" ON public."LLMModel" USING btree ("modelName");


-- ---------------------------------------------------------------------------
-- The two intersects. Design rule 2: capability lives on the model, performance
-- lives on the connection. There is no third place for either.
--
-- The foreign keys are NOT here. They are Item 11 of the plan, which also adds the
-- one relationship this schema has never had — UserAIConnection.provider to
-- AIProvider.code. Creating the columns here and the constraints there keeps each
-- item's acceptance separately checkable; the order is forced anyway, because a
-- foreign key cannot reference a table that does not exist yet.
-- ---------------------------------------------------------------------------

-- ProviderModelIntersect — which providers offer which models. The superset
-- relation: every model a provider offers, whatever server it was first seen on.
--
-- It carries nothing but the pair and when it was first seen, deliberately. Every
-- fact about a model belongs on LLMModel, and every fact about a pairing of model
-- and server belongs on ConnectionModelIntersect. A column here would be a third
-- home for something already owned, which is how the abandoned ProviderModel row
-- came to hold results that could not name the connection that produced them.
CREATE TABLE public."ProviderModelIntersect" (
    "providerCode" text NOT NULL,
    "modelId" text NOT NULL,
    "firstSeenAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT "ProviderModelIntersect_pkey" PRIMARY KEY ("providerCode", "modelId")
);

-- ConnectionModelIntersect — what one connection serves, what it measured, and
-- when it was last confirmed. The composite key is the identity: a model is a
-- fact about a connection once, however many times discovery runs.
--
-- connectionTestResults holds the per-test measurements — {durationMs, outcome,
-- at} keyed by test id. Keyed rather than a column per test for the same reason as
-- the model's results column: a new test is a registry entry, not a migration in
-- two chains and a change to two backends' scan code.
--
-- AND NO PERFORMANCE COLUMN. P2 was taken on 2026-10-30: durations only, and the
-- comparison against the user's limit happens at read time. A stored label would be
-- correct only for the limit in force when it was written, and having both a label
-- and the duration it came from is two representations of one fact. The item text
-- still says "and the performance column P2 decides"; P2 decided there is none, so
-- the duration lives inside connectionTestResults and nothing else is stored.
CREATE TABLE public."ConnectionModelIntersect" (
    "connectionId" integer NOT NULL,
    "modelId" text NOT NULL,
    "connectionTestResults" jsonb,
    "lastSeenAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT "ConnectionModelIntersect_pkey" PRIMARY KEY ("connectionId", "modelId")
);


-- ---------------------------------------------------------------------------
-- The foreign keys. This is the part of the redesign that makes the three
-- entities real relationships rather than conventions.
--
-- WHAT WAS THERE BEFORE: exactly one foreign key among these tables —
-- UserAIConnection.userId to User. UserAIConnection.provider and the abandoned
-- ProviderModel.providerCode were joined to AIProvider.code by text agreement
-- alone, which is how a change in one place could quietly orphan three others
-- and only a human reading the data would notice.
--
-- ON UPDATE CASCADE on every key below, matching UserAIConnection_userId_fkey and
-- the rest of this schema: a provider code or a connection id that changes takes
-- its references with it rather than leaving them pointing at the old value.
--
-- DELETE BEHAVIOUR IS A DESIGN STATEMENT, NOT A DEFAULT
--   ConnectionModelIntersect -> UserAIConnection   ON DELETE CASCADE
--       A deleted connection's findings go with it. A measurement of a server
--       that no longer exists is not a fact about anything.
--   ConnectionModelIntersect -> LLMModel           ON DELETE RESTRICT
--   ProviderModelIntersect   -> LLMModel           ON DELETE RESTRICT
--       A model with observations cannot be deleted out from under them. The
--       design's rule is that a capability result outlives its connections, and
--       this is the database enforcing it instead of an application check that a
--       future writer could forget.
--   ProviderModelIntersect   -> AIProvider         NO ACTION
--   UserAIConnection         -> AIProvider         NO ACTION
--       The item specifies the two model keys and the connection key; it says
--       nothing about what deleting a provider should do. NO ACTION is chosen
--       because it REFUSES — a provider cannot be removed while a connection or a
--       catalogue entry still names it — which is the same stance as the model
--       keys and cannot silently take data with it. Written out rather than left
--       implicit so the choice is visible and can be changed in one place.
--
-- PRE-FLIGHT: a foreign key fails on any row that does not resolve, and it fails
-- at the moment the migration runs, on a deployment. Checked first on the live
-- database: all 8 UserAIConnection rows name a code that exists in AIProvider
-- (deepseek, openrouter, ollama-local), and AIProvider.code carries
-- "AIProvider_code_key", a unique index — which is what allows it to be a foreign
-- key target at all.
ALTER TABLE public."ProviderModelIntersect"
    ADD CONSTRAINT "ProviderModelIntersect_providerCode_fkey"
    FOREIGN KEY ("providerCode") REFERENCES public."AIProvider"(code)
    ON UPDATE CASCADE ON DELETE NO ACTION;

ALTER TABLE public."ProviderModelIntersect"
    ADD CONSTRAINT "ProviderModelIntersect_modelId_fkey"
    FOREIGN KEY ("modelId") REFERENCES public."LLMModel"(id)
    ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE public."ConnectionModelIntersect"
    ADD CONSTRAINT "ConnectionModelIntersect_connectionId_fkey"
    FOREIGN KEY ("connectionId") REFERENCES public."UserAIConnection"("connectionId")
    ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE public."ConnectionModelIntersect"
    ADD CONSTRAINT "ConnectionModelIntersect_modelId_fkey"
    FOREIGN KEY ("modelId") REFERENCES public."LLMModel"(id)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- The key that has never existed. Adding it is what turns "the connection says
-- ollama-local" from a string a developer hopes matches into a relationship the
-- database maintains.
ALTER TABLE public."UserAIConnection"
    ADD CONSTRAINT "UserAIConnection_provider_fkey"
    FOREIGN KEY (provider) REFERENCES public."AIProvider"(code)
    ON UPDATE CASCADE ON DELETE NO ACTION;
