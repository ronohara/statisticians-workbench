-- A provider must have a default endpoint, so "no endpoint anywhere" is unrepresentable.
--
-- The Go deployed chain carries the same statements as
-- workbench-go/sawhorse/migrations/00017_ai_provider_default_endpoint_not_null.sql.
--
-- THE DEFECT THIS CLOSES
--
-- `UserAIConnection.endpoint` is nullable ON PURPOSE: NULL means "inherit my provider's
-- default", which is why the sample environment stores a connection with no endpoint of
-- its own. That is a deliberate absence, not a gap.
--
-- The gap is one level up. `AIProvider.defaultEndpoint` was also nullable, and nothing
-- prevented a provider row from having neither a default nor a connection-level endpoint.
-- A connection pointing at such a provider resolved to NO endpoint at all, and the failure
-- surfaced as `OPENAI_ENDPOINT_REQUIRED` — a configuration fault reported as an unknown
-- transport failure, three layers away from the row that caused it. Measured 2026-11-19:
-- the AI-testing page refused to test `sample-bikestore-AI` (connection 310, deepseek,
-- endpoint NULL) while chat on the same connection worked, because chat's resolver applied
-- the provider default and the test route read the raw column.
--
-- So the model answered "where is the endpoint?" with a chain of two nullable columns and
-- no rule joining them. This migration makes the chain total: every provider carries a
-- default, so every connection resolves to an endpoint, whatever it stores itself.
--
-- WHAT THIS DELIBERATELY DOES NOT DO
--
-- It does not move a URL into any connection row. The design record is explicit that a
-- provider's default endpoint lives in `AIProvider` and nowhere else
-- (`workbench-documents/project-design.md`, "One home for provider configuration"), so the
-- inheritance stays and the copy that would go stale is never created.
--
-- It does not invent an endpoint for a row that lacks one. If any provider has no default,
-- the guard below refuses the migration and names the providers, because the only honest
-- alternatives are an operator supplying the URL or that provider being removed — neither
-- of which a migration can decide.
--
-- It does not make `UserAIConnection.endpoint` NOT NULL. That column's NULL is the
-- inheritance, and removing it would force a copy into every row: the second home the
-- design forbids.

-- A blank endpoint is the same gap as a missing one: an empty string is falsy, so a resolver
-- that writes `endpoint or provider_default` treats it exactly as NULL and the connection
-- ends up with no endpoint at all. NOT NULL alone would admit it, so the guard covers both
-- and the CHECK below keeps it out afterwards.
DO $$
DECLARE
    offenders text;
BEGIN
    SELECT string_agg(code, ', ' ORDER BY code)
      INTO offenders
      FROM public."AIProvider"
     WHERE "defaultEndpoint" IS NULL
        OR btrim("defaultEndpoint") = '';

    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'AIProvider.defaultEndpoint is about to become NOT NULL, but % has no usable default endpoint. Give the provider an endpoint (an operator decision — this migration will not invent one), or remove the provider, then re-run.',
            offenders;
    END IF;
END
$$;

ALTER TABLE public."AIProvider"
    ALTER COLUMN "defaultEndpoint" SET NOT NULL;

-- An endpoint that is present but blank passes NOT NULL and still resolves to nothing.
ALTER TABLE public."AIProvider"
    DROP CONSTRAINT IF EXISTS "AIProvider_defaultEndpoint_not_blank";

ALTER TABLE public."AIProvider"
    ADD CONSTRAINT "AIProvider_defaultEndpoint_not_blank"
    CHECK (btrim("defaultEndpoint") <> '');
