# Installing the Statisticians Workbench — Open Source Edition

Instructions for getting the open source version running from source on Linux.

**Status: being proven step by step, 2026-11-18.** These steps are worked
through one at a time on the `mint22open` test bed (Mint 22.3), and each is
corrected as it is proven. Steps marked **[PROVEN]** have been executed on that
machine and their checks passed; steps marked **[UNPROVEN]** have not, and are
the ones expected to need revision.

- Step 1, prerequisites — **[PROVEN]** 2026-11-18
- Step 3, private cluster, role and databases — rewritten 2026-11-18 to the
  private-cluster model (port 9431); **not yet run**
- Step 6, schema — now one file (`db/baseline`, re-dumped at HEAD 2026-11-18);
  `db/migrations/` is history and is not applied. **Not yet run**
- Step 7, seed — now runs `scripts/workbench-seed.py`, the Python port of
  `workbench-go/cmd/workbench-seed`; **not yet run**

Each step states how to check that it worked. Do not skip the check — a later
step failing usually means an earlier one silently did not do what it claimed.

---

## 0. What is being installed

Three pieces:

| Piece | Directory | Runs on | Serves |
|---|---|---|---|
| Backend (Python / FastAPI) | `backend/` | port 8000 | `/api/*` |
| Frontend (Next.js) | `frontend/` | port 3000 | the web UI |
| Database (PostgreSQL) | `db/` holds the schema | private cluster on **9431** | both of the above |

The frontend proxies `/api/*` calls to the backend on `127.0.0.1:8000`
(`frontend/next.config.mjs`), so both must be running for the UI to work.

---

## 1. Prerequisites

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-dev \
                    postgresql postgresql-client \
                    build-essential libpq-dev
```

Node.js, npm and pnpm:

```bash
sudo apt install -y nodejs npm
npm install -g pnpm
```

**Check:**

```bash
git --version
python3 --version
python3 -c 'import venv; print("venv ok")'
gcc --version | head -1
make --version | head -1
test -f /usr/include/postgresql/libpq-fe.h && echo 'libpq-dev ok'
node --version
npm --version
pnpm --version
```

Every line must print a version; the two `echo` checks must print `ok`.

### On the Node version

**The archive's Node 18.19.1 is what this install uses, and it works.** Measured
on `mint22open` 2026-11-18: `node v18.19.1`, `npm 9.2.0`, and `pnpm 12.21.0`
installed by `npm install -g pnpm` — the whole chain from Mint's own archive,
with no third-party repository.

That is deliberate, not a compromise. Mint 22.3 is a deployment target, and the
point of testing there is to prove the product works on the Node a stock Mint
user actually has. Node 18 is end-of-life upstream and no longer receives
security fixes, so this is a fact about the test bed rather than a
recommendation: a production deployment should use a supported Node, and moving
to one is a packaging decision for the commercial side.

An earlier draft of this file required Node 20 or newer and sent the reader to
NodeSource. That was an inference from Next.js's stated support matrix, not a
measurement, and it was wrong for this tree — recorded here so the requirement
is not reintroduced without evidence.

### PostgreSQL is installed here, and set up later

`postgresql` is in the list above because it is a prerequisite, but the install
itself only creates the machine's default cluster, `16/main` on 5432. The
Workbench does **not** use that cluster. It gets one of its own, `16/workbench`
on **9431**, created in **step 3**; applying the schema is **step 6**. Installing
the package now is what supplies the binaries both clusters run from.

If the machine previously had PostgreSQL that must not be reused — a rebuilt
test bed, say — purge it first, then install:

```bash
sudo pg_dropcluster --stop 16 main
sudo apt-get purge -y postgresql-16 postgresql-client-16 \
                      postgresql-common postgresql-client-common
sudo apt-get autoremove --purge -y
sudo rm -rf /etc/postgresql /var/lib/postgresql /var/log/postgresql \
            /var/cache/postgresql
sudo deluser --system postgres
```

`apt-get autoremove --purge` can take unrelated orphaned packages with it — on
`mint22open` it removed `sysstat` and `node-xtend`. Reinstall anything wanted
back with `apt-get install -y <name>`.

---

## 2. Clone the repository

```bash
cd ~
git clone https://github.com/ronohara/statisticians-workbench.git
cd statisticians-workbench
```

**Check:** `ls` shows `backend/`, `db/`, `frontend/`, `scripts/`.

---

## 3. Create the private cluster, its role and both databases

**The Workbench runs on a PostgreSQL cluster of its own, on port 9431 — not on
the machine's default cluster on 5432.** This is the private-cluster model
described in `workbench-documents/workbench-using-private-cluster-plan.html`,
and it is the arrangement every supported installation uses.

The reason is boundary, not preference. The private cluster holds the product's
internal state and the upload repository, and nothing else. The distro's own
cluster on 5432 may hold your databases; the Workbench never starts, stops,
configures or connects to it. Port 9431 is also adjacent to 9432, which
`msaccess-endpoint-ng` uses for its bundled cluster, so the two cannot collide.

> **This source install does not write the package's ownership marker.**
> `16/workbench/.workbench-managed` exists so a `.deb`'s `postrm` can prove the
> cluster is ours before dropping it on purge. Nothing packaged is installed
> here, so there is no `postrm` and no marker. Teardown is by hand — §13.

### 3a. Create the cluster

Mint's `postgresql` package creates `16/main` on 5432. Leave it alone; add ours
beside it.

```bash
sudo pg_lsclusters                      # expect 16/main on 5432, online
sudo pg_createcluster 16 workbench --port 9431 \
     --locale=en_US.UTF-8 --encoding=UTF8
```

**Check:**

```bash
pg_lsclusters                          # now two rows: 16/main 5432, 16/workbench 9431
pg_isready -p 9431                      # "accepting connections"
```

If `pg_isready` says no response, the cluster was created stopped. Start it
through its unit rather than with `--start`, so an administrator's `policy-rc.d`
is respected:

```bash
sudo systemctl start postgresql@16-workbench
pg_isready -p 9431 -t 30
```

Re-running `pg_createcluster` on an existing cluster refuses. That is the guard,
not a fault — check `pg_lsclusters` before concluding anything.

### 3b. Create the role and both databases

**Both databases are created here, and the role needs no `CREATEDB`.** At
startup the backend calls `ensure_data_database`, which returns immediately when
`workbench_data` already exists (`backend/src/postgres_data_manager.py`);
creating it now is what removes the privilege, rather than granting a wider one
than the install needs.

**Both databases are pinned to UTC here, and this is not optional.** A PostgreSQL
database inherits the cluster's timezone at creation, and the cluster inherited
whatever the installing machine was set to. The application pins its own pooled
connections (`_init_connection` in `backend/main.py`), so the application would
be unaffected either way — but every *other* consumer would not: a `psql`
session, an operator's query, the packaging importer. The packaged build carries
this as migration `0026_database_timezone_utc.sql`; this install applies no
migrations, so it is done explicitly below instead.

`psql` runs as `postgres` over peer auth on the socket, so no password is
consulted and none crosses the wire.

```bash
sudo -u postgres psql -p 9431 <<'SQL'
CREATE ROLE workbench WITH LOGIN PASSWORD 'change-this-password';
ALTER ROLE workbench NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE workbench      OWNER workbench;
CREATE DATABASE workbench_data OWNER workbench;
ALTER DATABASE workbench      SET timezone = 'UTC';
ALTER DATABASE workbench_data SET timezone = 'UTC';
SQL
```

**Check — the role exists with the right attributes:**

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin \
   FROM pg_roles WHERE rolname='workbench';"
```

Expect `workbench | f | f | f | t`. A `t` in any of the first three is a widened
grant that the application does not need.

**Check — both databases exist and are owned by the role:**

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT datname, pg_get_userbyid(datdba) AS owner \
   FROM pg_database WHERE datname LIKE 'workbench%';"
```

Expect two rows, both owned by `workbench`.

**Check — both databases default to UTC:**

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT d.datname, s.setconfig FROM pg_db_role_setting s \
   JOIN pg_database d ON d.oid = s.setdatabase ORDER BY 1;"
```

Expect `{TimeZone=UTC}` on both rows. An empty result means the `ALTER DATABASE`
statements did not run — worth fixing now, because the difference only shows up
later, in a psql session that reports a different time from the application.

**Check — the credential authenticates over TCP:**

```bash
PGPASSWORD='change-this-password' psql -h 127.0.0.1 -p 9431 \
  -U workbench -d workbench -c 'SELECT current_user, current_database();'
```

One row, `workbench | workbench`. A `no password supplied` here means
`pg_hba.conf` on the new cluster was not generated as expected — that is a
finding to record, not to work around.

### 3c. Confirm 5432 was not touched

The default cluster must still be exactly as it was:

```bash
pg_lsclusters                          # 16/main still online on 5432
sudo -u postgres psql -p 5432 -tAc \
  "SELECT count(*) FROM pg_database WHERE datname LIKE 'workbench%';"
```

The count must be **0**. If the role or either database appears on 5432, the
commands above ran against the wrong cluster — stop and drop them there before
continuing, rather than leaving a second copy the application will never use.

---

## 4. Create the Python virtual environment

```bash
cd ~/statisticians-workbench/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

`requirements.txt` is the runtime subset — the packages the backend actually
imports, not the development and test stack. It pins versions that are known to
work together.

**Check:**

```bash
./venv/bin/python -c "import fastapi, asyncpg, pandas, uvicorn; print('ok')"
```

Prints `ok`. If `psycopg2` or `pymssql` fail to build, the build headers from
step 1 are missing, or no wheel exists for this Python version — record which
package failed here rather than working around it.

`pymssql` is only needed for Microsoft SQL Server connections; `pymssql` and
`psycopg2-binary` both normally install as prebuilt wheels.

---

## 5. Create the environment files

Two `.env` files are needed: one for the backend, one for the frontend. **Neither
is in the repository** — they are gitignored, because they hold secrets.

Generate two secrets first:

```bash
openssl rand -base64 32      # NEXTAUTH_SECRET  — copy this value
openssl rand -hex 32         # ENCRYPTION_KEY   — must be exactly 64 hex characters
```

### 5a. `backend/.env`

```bash
cat > ~/statisticians-workbench/backend/.env <<'ENV'
DATABASE_URL=postgresql://workbench:change-this-password@127.0.0.1:9431/workbench
NEXTAUTH_SECRET=<paste the base64 value>
ENCRYPTION_KEY=<paste the 64-character hex value>
ALLOWED_ORIGINS=http://localhost:3000
ENVIRONMENT=development
ENV
```

What each does, and what breaks without it:

- `DATABASE_URL` — required. The backend refuses to start without it
  (`backend/main.py`, raises `RuntimeError("DATABASE_URL environment variable not set")`).
  **The port is 9431**, the private cluster from §3 — never 5432, which belongs to
  the machine's own PostgreSQL. `workbench_data` is derived from this URL by
  swapping the database name, so this one line points both pools at the cluster.
- `ENCRYPTION_KEY` — required, and **must be exactly 64 hexadecimal characters**.
  The backend raises at import time otherwise (`backend/src/utils/encryption.py`).
  It encrypts stored connection passwords; if it changes later, previously saved
  credentials can no longer be decrypted.
- `NEXTAUTH_SECRET` — signs the session token. The **frontend must use the same
  value**, because the frontend mints the token and the backend verifies it.
- `ALLOWED_ORIGINS` — CORS for the browser calling the API.
- `ENVIRONMENT` — `development` enables the rotated log file
  (`logs/backend.log`); production logs to the supervisor instead.

### 5b. `frontend/.env`

```bash
cat > ~/statisticians-workbench/frontend/.env <<'ENV'
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<the same value as backend/.env>
BACKEND_URL=http://127.0.0.1:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
ENV
```

**Check:**

```bash
cd ~/statisticians-workbench/backend
./venv/bin/python -c "
import os; from dotenv import load_dotenv; load_dotenv()
k = os.getenv('ENCRYPTION_KEY')
print('DATABASE_URL set:', bool(os.getenv('DATABASE_URL')))
print('ENCRYPTION_KEY length:', len(k or ''), '(must be 64)')
print('NEXTAUTH_SECRET set:', bool(os.getenv('NEXTAUTH_SECRET')))
"
```

All three lines must be true and the length must read 64.

> **Outstanding:** there is no longer a script that generates these files. The
> old `scripts/generate-env-files.sh` was withdrawn (it targeted a database
> arrangement that no longer exists, and rotated the application role's
> password). A replacement that writes both files and generates both secrets
> safely is still to be written — see §11.

---

## 6. Create the schema

**One file, one command.** `db/baseline/0000_baseline.sql` is a schema-only dump
of the current database — every table, column, index, constraint and sequence at
this release. Nothing else has to be applied.

Apply it to **`workbench` on the private cluster, port 9431** — the database
created in §3. `workbench_data` is already there and empty; it is plain storage
and needs no schema.

```bash
cd ~/statisticians-workbench
export PGPASSWORD='change-this-password'
export PGHOST=127.0.0.1 PGPORT=9431 PGUSER=workbench PGDATABASE=workbench
```

**Check the target before applying anything.** 3c tested for the role and
databases, not for tables, so it would not catch a schema applied to the wrong
cluster:

```bash
psql -tAc 'SELECT current_database(), inet_server_port();'
```

Expect `workbench|9431`. Only then:

```bash
psql -v ON_ERROR_STOP=1 -f db/baseline/0000_baseline.sql
```

**Check:** the command exits 0 and prints no `ERROR:` lines. Then:

```bash
psql -c '\dt' | wc -l
psql -c '\d "GlobalSettings"'
```

The first prints a table count — **30** tables plus the header lines `wc` counts.
The second must show `registrationMode`, and `\d "UserDataset"` must show
`materializedAt` and `materializeError`. Those three columns are the quick proof
that this is the current schema rather than an older snapshot.

### `db/migrations/` is history, not an install step

The numbered files record how the schema reached its present shape. They are
**not** applied during an install, and several cannot be: `0001` issues plain
`CREATE TABLE` for tables the baseline already contains, so replaying them from
the start fails on the first file.

They remain in the repository because they document the changes, and because
the Go backend's `sawhorse` lineage mirrors them. A reader comparing the two
should treat `db/baseline` as the schema and `db/migrations` as the record of
how it got there.

`db/migrations/0006_reconcile_timestamps.py` is a Python data-reconciliation
script, not SQL. It is only relevant to a database that predates the timestamp
work, and never runs during a fresh install.

---

## 7. Seed the database

The schema is empty. `db/baseline` contains no `INSERT` statements, and the
application needs a good deal more than an empty schema before it can be used:
without the `GlobalSettings` row, registration fails with a 500
(`api.register.settings_not_found`), and there is no administrator account.

Run the seed program:

```bash
cd ~/statisticians-workbench
backend/venv/bin/python scripts/workbench-seed.py
```

It reads `DATABASE_URL` from the environment, or from `backend/.env`, so no
argument is needed. It runs in **one transaction** and is **idempotent** — a
second run changes nothing.

What it creates:

- `GlobalSettings` — the single row (id = 1), with the welcome message
- `UserGroup` — 100 groups, `00` (Default) through `99`
- `User` — `admin@example.com` / `admin123` (administrator) and
  `exampleuser@example.com` / `User1234#`
- `AIProvider` — DeepSeek, OpenRouter, Ollama local and remote, all enabled
- `VisualizationType` — the ten built-in chart types

**Check:**

```bash
psql -c 'SELECT id, "registrationMode", "passwordPolicy", "emailSender", "publicUrl" FROM "GlobalSettings";'
psql -c 'SELECT count(*) FROM "UserGroup";'
psql -c 'SELECT email, "isAdmin" FROM "User" ORDER BY email;'
psql -c 'SELECT code FROM "AIProvider" ORDER BY code;'
psql -c 'SELECT count(*) FROM "VisualizationType";'
```

Expected: one settings row with `registrationMode = 0`; **100** groups; two users,
with `admin@example.com` marked `t`; four providers; **10** visualization types.

Re-run the same command and confirm the counts are unchanged — that is the
idempotency check, and it exercises every `ON CONFLICT` clause.

### If the seed program is unavailable

The minimum the application needs is the settings row; everything else can be
created through the UI once an administrator exists. This is enough to register a
user, but **not** enough to have an administrator:

```bash
psql -c 'INSERT INTO "GlobalSettings" (id) VALUES (1) ON CONFLICT (id) DO NOTHING;'
```

### Two placeholder values

`emailSender` and `publicUrl` default to placeholders and should be changed
before the installation is used for anything real:

- `emailSender` — `no-reply@replace-with-your-domain`
- `publicUrl` — `https://replace-with-your-external-host-name`

Both are editable from the admin pages once an administrator exists.

---

## 8. Start the backend

```bash
cd ~/statisticians-workbench
./scripts/start-backend.sh
```

That script activates `backend/venv`, loads `backend/.env`, and runs
`python main.py`, which starts uvicorn on `0.0.0.0:8000` with `reload=True`.

On first start the backend creates `workbench_data` if it is absent. Expect log
lines naming the database cluster, the pool, and the data database.

**Check** — in a second terminal:

```bash
curl -s http://localhost:8000/api/health
```

Expected, in substance:

```json
{"status":"healthy","version":"0.12.2","backend":"python",
 "database":{"pool_initialized":true,"host":"127.0.0.1","port":9431}}
```

`"backend":"python"` confirms it is this backend and not the Go one;
`pool_initialized:true` confirms the database connection. If the port or host
look wrong, `DATABASE_URL` is wrong — the health body reports the cluster it
parsed from it, deliberately, so the answer is available even when the database
is unreachable.

Leave this running. `logs/backend.log` in the repository root carries the same
lines with timestamps, which is easier to read than a terminal.

---

## 9. Build and start the frontend

```bash
cd ~/statisticians-workbench/frontend
pnpm install
pnpm build
pnpm start
```

`pnpm start` serves the production build on port 3000. This project does **not**
use `pnpm dev` for verification — it misses build errors.

If `pnpm install` reports build-script warnings, run `pnpm approve-builds` and
select all packages, then re-run.

**Check:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/
```

Expect a redirect code (`307`) for an unauthenticated request — that is the
login redirect, not an error. Then open `http://localhost:3000` in a browser:
the login page should render.

---

## 10. Log in as the administrator

The seed in step 7 created `admin@example.com` with the password `admin123` and
`isAdmin = true`, so there is nothing to promote.

1. Open `http://localhost:3000/login` and sign in as `admin@example.com` /
   `admin123`.
2. **Change that password immediately** — it is published in this document. Use
   the profile page, or the admin user page.
3. Set a real email address for the administrator and verify it, so password
   reset and notification email have somewhere to go.

**Check:** the sidebar shows the admin entries (`/admin/users`,
`/admin/setup/options`), and `/admin/users` lists both seeded accounts.

### If you did not run the seed program

A user registered at `/register` is **not** an administrator: `User.isAdmin`
defaults to `false` and no code path promotes the first registration. Promote it
by hand, then log out and back in — the session token carries the flag, so a stale
session will not show the admin pages:

```bash
psql -c 'UPDATE "User" SET "isAdmin" = true WHERE email = '\''you@example.com'\'';'
```

---

## 11. Known gaps, and one deferral

These are the parts this document cannot yet describe honestly.

**(a) The `.env` creation process needs rebuilding.** The old
`generate-env-files.sh` was withdrawn — it targeted the pre-0.12 database
arrangement, rotated the application role's password (breaking every running
backend), and `chown -R`ed the whole checkout to another user. A replacement
must write both files, generate `NEXTAUTH_SECRET` and a 64-character
`ENCRYPTION_KEY`, and never overwrite an existing `.env` without saying so.

**(b) The seed program is unproven.** `scripts/workbench-seed.py` is a port of
`workbench-go/cmd/workbench-seed`, and its data was compared against the Go
source field by field — but it has not been run against a database yet. Step 7
is the first place that will show whether it works. If it fails, the manual
`INSERT` in step 7 and the promotion in step 10 still get an installation to a
working administrator.

**(c) Translations are not yet shipped.** `backend/locales/` and the import
script are not in this repository, so the interface runs English-only. Shipping
them is a later step, together with the extract → translate → import pipeline.

**(d) Platform support is Linux only.** This repository is scoped to Linux.
Windows and macOS packaging belong to the commercial side.

### Deferred: upgrading an existing source installation

**Not covered, and deliberately not built yet.** A reader who pulls new commits
over an existing installation has a database one release behind its code, and
this document says nothing about how to move it forward.

That is a **record** problem — knowing which of the numbered files in
`db/migrations/` have already been applied — not a migration-engine problem.
When the first second release exists, this document gains a procedure, and
`db/migrations/` becomes the input to it rather than history.

**Why no runner is being written now.** `sawhorse` is not a migration engine:
`workbench-go/sawhorse/migrations/migrations.go` is a 17-line `//go:embed`, and
the runner behind it is the third-party library `pressly/goose`, invoked from
116 lines in `sawhorse/internal/core/create_database.go`. Its machinery — an
applied-version table, advisory locking, per-migration transactions — exists to
make an **unattended deployment upgrade** safe. The open source edition is not a
deployment: it is installed once, from source, by the person running it. Goose's
job belongs to the packaged product, and reproducing it here would be building
for a workflow that does not yet exist.

---

## 12. Verification checklist

Run top to bottom after a fresh install. Every line should succeed.

```bash
# backend health, and which backend answered
curl -s http://localhost:8000/api/health

# frontend answers (307 = login redirect)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/

# schema present: 30 tables from the baseline (plus wc's header lines),
# and the columns that prove it is current
psql -c '\dt' | wc -l
psql -c '\d "GlobalSettings"' | grep registrationMode
psql -c '\d "UserDataset"' | grep materialize

# the seed landed: one settings row, 100 groups, 2 users, 4 providers, 10 types
psql -c 'SELECT count(*) FROM "GlobalSettings";'
psql -c 'SELECT count(*) FROM "UserGroup";'
psql -c 'SELECT count(*) FROM "User";'
psql -c 'SELECT count(*) FROM "AIProvider";'
psql -c 'SELECT count(*) FROM "VisualizationType";'

# an administrator exists
psql -c 'SELECT email FROM "User" WHERE "isAdmin" = true;'
```

Then, in the browser: log in as `admin@example.com` / `admin123`, change that
password, and open `/admin/users` — a page that needs administrator rights — and
confirm no error banner appears.

---

## 13. Starting over

### 13a. Clear the data and start again

To discard both databases and re-create them, leaving the cluster in place:

```bash
sudo -u postgres psql -p 9431 <<'SQL'
DROP DATABASE IF EXISTS workbench_data;
DROP DATABASE IF EXISTS workbench;
DROP ROLE IF EXISTS workbench;
SQL
```

Then repeat from step 3b. The cluster, the Python virtual environment and
`node_modules` do not need rebuilding unless `requirements.txt` or
`package.json` changed.

### 13b. Remove the cluster entirely

Only when the whole installation is being abandoned. **The cluster name
`workbench` in this command is what protects anything else** — it names ours
specifically, so `16/main` and every database in it are untouched.

```bash
pg_lsclusters                                    # confirm 16/workbench on 9431
sudo pg_dropcluster --stop 16 workbench
pg_lsclusters                                    # 16/workbench gone; 16/main still online
```

Then remove the `DATABASE_URL` line's credentials from `backend/.env`, or the
file entirely — the next install generates fresh ones.

**Do not run `apt-get purge postgresql-*` to tidy up.** That removes the distro's
package and `16/main` with it, taking any database that is not ours. §1 carries
the full purge sequence, and it is only for a machine being rebuilt.
