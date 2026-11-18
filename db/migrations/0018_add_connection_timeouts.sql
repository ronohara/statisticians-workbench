-- AI connection timeouts: how long the network may take, and how long a probe may take.
--
-- Plan: workbench-AI-timeout-policy-plan.html, Item 2.
-- Mirrors sawhorse/migrations/00008_add_connection_timeouts.sql so the Python dev
-- database gains the columns when migrated independently of sawhorse.
--
-- WHY THESE LIVE ON THE CONNECTION AND NOT ON THE PAIR
-- `ConnectionModelIntersect."timeoutSeconds"` already bounds how long a call may run,
-- and it belongs there because a model on a slow host needs more time than the same
-- model on a fast one. A CONNECT timeout is a different question, asked earlier: the
-- TCP connect reaches `UserAIConnection."endpoint"` before any model is named, so a
-- per-pair connect timeout could only ever hold the same value for every model on that
-- connection. Storing it on the pair would be a column whose granularity is a lie.
--
-- WHY TWO COLUMNS AND NOT ONE
-- Two failures were sharing one number, which is the defect this migration removes:
--
--   connectTimeoutSeconds  nothing answered at all — a dead host, a firewall dropping
--                          SYN, a wrong address. Knowable in seconds, and today the
--                          kernel decides instead (net.ipv4.tcp_syn_retries = 6 gives
--                          about 127 s on this machine, which is not a product decision).
--   probeTimeoutSeconds    connected, asked, and the answer never came — a slow or hung
--                          model. Legitimately minutes, so it needs its own budget.
--
-- They are separate because one is a fault and the other is patience.

-- NULL MEANS "INHERIT", NOT "ZERO"
-- A connection with no opinion takes the workbench default. The columns are nullable so
-- the resolver can tell "not configured" from "configured to the smallest legal value",
-- the distinction 0017 established for the tuning columns. A timeout of 0 is not a
-- setting — it would refuse everything.
ALTER TABLE public."UserAIConnection"
    ADD COLUMN IF NOT EXISTS "connectTimeoutSeconds" integer;

ALTER TABLE public."UserAIConnection"
    ADD COLUMN IF NOT EXISTS "probeTimeoutSeconds" integer;

-- The workbench-wide defaults, on the settings row that already exists.
--
-- NOT NULL with a DEFAULT, for the reason 0017 gives: a nullable global would put the
-- real value in code as a fallback, which is the hidden default the No Silent
-- Enhancement rule forbids. The constants in connection_timeouts.py and
-- connection_timeouts.go are the seed for a new row, not an arbiter of what is in force.
--
-- 10 SECONDS FOR CONNECT IS A DELIBERATE TIGHTENING, and the only behavioural change
-- this migration makes. What it replaces is not a number but an absence: Go built
-- `&http.Client{}` with no Transport at all, so the dial had no timeout and the kernel's
-- SYN backoff decided (about 127 s); Python passed the whole 300 s as httpx's connect
-- phase. Both meant an unreachable host cost minutes. Ten seconds is generous for a LAN
-- and still tolerable for a WAN endpoint behind a proxy, and a deployment that needs
-- longer sets it per connection or raises the default — which is the point of making it
-- data rather than compiling it in.
--
-- 300 SECONDS FOR PROBE IS NOT A CHANGE. It is the value `DEFAULT_TIMEOUT` has carried
-- in both backends since the probes were written
-- (backend/src/chat/probe_vocabulary.py, workbench-go/internal/llm/probevocab), chosen
-- because a CPU-hosted 27B model takes minutes and a probe that times out on a
-- slow-but-good model records a false failure. Seeding the row with it means nobody's
-- behaviour changes on migration; what changes is that it can now be edited.
ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "defaultConnectTimeoutSeconds" integer NOT NULL DEFAULT 10;

ALTER TABLE public."GlobalSettings"
    ADD COLUMN IF NOT EXISTS "defaultProbeTimeoutSeconds" integer NOT NULL DEFAULT 300;

-- ============================================================
-- RANGE CHECKS: A BACKSTOP, NOT THE REFUSAL THE USER SEES
-- ============================================================
--
-- The API validates first and produces the coded, translated refusal; these constraints
-- are what stops a write that bypasses the API — a hand-run UPDATE, a future script, a
-- seed file. A constraint firing means the code wrote something it should have refused,
-- which is a bug, and a 500 is the honest answer for it. 0016 and 0017 both state this
-- and it is not restated in full here.
--
-- `> 0` rather than a band: a connect budget of 1 s is wrong for a WAN endpoint but it
-- is not invalid, and the person who owns the deployment is the one who knows. The
-- UPPER bounds are deliberately NOT here — they are product judgements held in the
-- backend (ConnectTimeoutCeiling / ProbeTimeoutCeiling), following the precedent
-- MAX_TIMEOUT_SECONDS set: a constraint says "this can never be valid", and a ceiling
-- is a number someone might one day raise.
ALTER TABLE public."UserAIConnection"
    ADD CONSTRAINT "UserAIConnection_connectTimeoutSeconds_positive"
    CHECK ("connectTimeoutSeconds" IS NULL OR "connectTimeoutSeconds" > 0);

ALTER TABLE public."UserAIConnection"
    ADD CONSTRAINT "UserAIConnection_probeTimeoutSeconds_positive"
    CHECK ("probeTimeoutSeconds" IS NULL OR "probeTimeoutSeconds" > 0);

ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_defaultConnectTimeoutSeconds_positive"
    CHECK ("defaultConnectTimeoutSeconds" > 0);

ALTER TABLE public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_defaultProbeTimeoutSeconds_positive"
    CHECK ("defaultProbeTimeoutSeconds" > 0);

-- ============================================================
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
-- ============================================================
--
-- No backfill of the connections. Every existing row keeps NULL for both, which means
-- "this connection has no opinion" and lets the global default apply. Backfilling would
-- freeze today's default into every row and make a later change to the default silently
-- ineffective for all of them.
--
-- No constraint enforcing connectTimeoutSeconds < probeTimeoutSeconds (or < the pair's
-- timeoutSeconds). Two reasons. The values live in different tables — resolving them in
-- a CHECK would need a subquery, which PostgreSQL will not allow in a CHECK at all. And
-- the plan decided (D6) to refuse such a write at the API and clamp at use, because a
-- later change to one value can invalidate the other with no write to refuse. The clamp
-- is in the resolver, not here.
--
-- No index. Both columns are read by primary key on a row the caller already has.
