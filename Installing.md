# Installing the Statisticians Workbench — Open Source Edition

A step-by-step guide to running the open source edition from source on Linux.

## Before you start

**Supported systems:** Ubuntu 24.04 LTS and derivatives. The reference system is
Linux Mint 22.3, which is built on the Ubuntu 24.04 base.

| | |
|---|---|
| Distribution | Linux Mint 22.3 (or Ubuntu 24.04 and derivatives) |
| Architecture | x86_64 |
| PostgreSQL | 16, from the distribution archive |
| Node.js | **22 LTS** — the archive's 18.x is too old to build the frontend; step 1 replaces it |

You will need `sudo`, an internet connection, and about 1 GB of free disk space.

The Workbench is three pieces:

| Piece | Directory | Port | Serves |
|---|---|---|---|
| Backend (Python / FastAPI) | `backend/` | 8000 | `/api/*` |
| Frontend (Next.js) | `frontend/` | 3000 | the web interface |
| Database (PostgreSQL) | `db/` holds the schema | **9431** | both of the above |

The frontend proxies `/api/*` to the backend on `127.0.0.1:8000`, so both must be
running for the interface to work.

Each step below ends with a **check**. Do not skip one: when a later step fails,
the cause is almost always an earlier step that did not do what it claimed.

---

## 1. Install the prerequisites

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-dev \
                    postgresql postgresql-client \
                    build-essential libpq-dev
```

### Node.js

The frontend is built with Next.js 16, which requires **Node 20.9 or newer**.
The version in the Ubuntu and Mint archives is 18.x, and it cannot build this
project — the build stops immediately with an error naming the required version.

Install Node 22 LTS from NodeSource:

```bash
sudo apt-get install -y ca-certificates curl gnupg
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

NodeSource's script writes its own repository configuration and replaces the
distribution's `nodejs` package. If the machine already has NodeSource packages
for an older major version, remove them first so the new repository is
unambiguous:

```bash
sudo apt-get purge -y nodejs
sudo rm -f /etc/apt/sources.list.d/nodesource.list
sudo rm -f /etc/apt/sources.list.d/nodesource.sources
```

Then install pnpm:

```bash
sudo npm install -g pnpm
```

### Check

```bash
git --version
python3 --version
python3 -c 'import venv; print("venv ok")'
gcc --version | head -1
make --version | head -1
test -f /usr/include/postgresql/libpq-fe.h && echo 'libpq-dev ok'
npm --version
pnpm --version
```

Every line prints a version; the two `echo` checks print `ok`.

Then confirm Node is new enough — this line exits with an error if it is not:

```bash
node -e 'const [a,b]=process.versions.node.split(".").map(Number);
         if (a < 20 || (a === 20 && b < 9)) {
           console.error("Node " + process.versions.node + " is below 20.9.0 — the frontend cannot be built");
           process.exit(1);
         }
         console.log("Node " + process.versions.node + " — new enough");'
```

---

## 2. Clone the repository

```bash
cd ~
git clone https://github.com/ronohara/statisticians-workbench.git
cd statisticians-workbench
```

**Check:** `ls` shows `backend/`, `db/`, `frontend/`, `scripts/`.

---

## 3. Create the database

The Workbench runs on **a PostgreSQL cluster of its own, on port 9431**. It never
uses the machine's default cluster on 5432 — that one may hold your own
databases, and this installation leaves it untouched.

The application role needs no `CREATEDB`, because both databases are created here
rather than at runtime. Both are pinned to UTC, so timestamps read the same from
`psql` as they do in the application.

### 3a. Create the cluster

```bash
sudo pg_lsclusters                      # the default cluster, 16/main on 5432
sudo pg_createcluster 16 workbench --port 9431 \
     --locale=en_US.UTF-8 --encoding=UTF8
```

**Check:**

```bash
pg_lsclusters                          # two rows: 16/main on 5432, 16/workbench on 9431
pg_isready -p 9431                     # "accepting connections"
```

The new cluster is created stopped. If `pg_isready` reports no response, start it
through its systemd unit:

```bash
sudo systemctl start postgresql@16-workbench
pg_isready -p 9431 -t 30
```

Running `pg_createcluster` again on an existing cluster refuses with
`cluster configuration already exists`. That is the guard working, not a fault.

### 3b. Create the role and both databases

`psql` runs as the `postgres` system user over peer authentication, so no
password is consulted.

**Change the password below to one of your own before running it**, and use the
same value in step 5.

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

**Check — the role has the right attributes.** Expect `workbench | f | f | f | t`:

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin \
   FROM pg_roles WHERE rolname='workbench';"
```

**Check — both databases exist and are owned by the role.** Expect two rows:

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT datname, pg_get_userbyid(datdba) AS owner \
   FROM pg_database WHERE datname LIKE 'workbench%';"
```

**Check — both default to UTC.** Expect `{TimeZone=UTC}` on both rows:

```bash
sudo -u postgres psql -p 9431 -c \
  "SELECT d.datname, s.setconfig FROM pg_db_role_setting s \
   JOIN pg_database d ON d.oid = s.setdatabase ORDER BY 1;"
```

**Check — the credential works over TCP.** Expect one row, `workbench | workbench`:

```bash
PGPASSWORD='change-this-password' psql -h 127.0.0.1 -p 9431 \
  -U workbench -d workbench -c 'SELECT current_user, current_database();'
```

### 3c. Confirm the default cluster was not touched

```bash
pg_lsclusters                          # 16/main still online on 5432
sudo -u postgres psql -p 5432 -tAc \
  "SELECT count(*) FROM pg_database WHERE datname LIKE 'workbench%';"
```

The count must be **0**.

---

## 4. Create the Python environment

```bash
cd ~/statisticians-workbench/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

`requirements.txt` pins the runtime dependencies — the packages the backend
imports, not the development and test tooling. They all install as prebuilt
wheels; no compiler is needed beyond what step 1 installed. The environment is
about 300 MB.

**If `backend/venv` already exists, delete it first.** A virtual environment
cannot be moved: every script inside it records an absolute path to its own
interpreter, so a moved or relocated environment breaks in a confusing way —
`pip` fails saying a file is missing that is plainly there.

```bash
rm -rf ~/statisticians-workbench/backend/venv
```

**Check — the environment knows where it is.** This must print the path of the
`backend/venv` you are standing in:

```bash
./venv/bin/python -c 'import sys; print(sys.prefix)'
```

**Check — the dependencies load:**

```bash
./venv/bin/python -c "import fastapi, asyncpg, pandas, uvicorn; print('ok')"
```

Prints `ok`.

---

## 5. Create the configuration

One file holds the configuration, and both halves of the application read it
through a symbolic link:

```
config/workbench.env            the configuration
backend/.env   -> ../config/workbench.env
frontend/.env  -> ../config/workbench.env
```

This is the same arrangement the packaged product uses, and it exists for one
reason: `NEXTAUTH_SECRET` and `ENCRYPTION_KEY` must be identical in both halves —
the frontend mints the session token and the backend verifies it. One file makes
that a fact rather than two copies that have to be kept in agreement.

Run the generator, passing **the database password you chose in step 3b** — it
must use the password the role already has, and it will not guess one:

```bash
cd ~/statisticians-workbench
WORKBENCH_DB_PASSWORD='change-this-password' ./scripts/generate-env-files.sh
```

It writes the configuration, generates both secrets, creates both links and
verifies them, then confirms the database credential actually authenticates.

If the role does not exist yet — because you have not done step 3b — run
`./scripts/generate-env-files.sh` without the variable. It will generate a
password and print the SQL that creates the role with it, which you then run.

Notes on how it behaves:

- **It requires the database cluster to be running** (step 3). If it is not, the
  script stops without writing anything — a config written against a cluster
  that does not exist fails much later, at step 8.
- **It will not overwrite an existing configuration** unless you pass `--force`,
  and `--force` replaces it outright without keeping a copy. Back the file up
  yourself if you want the old secrets: a new `ENCRYPTION_KEY` makes every stored
  connection password undecryptable, and a new `NEXTAUTH_SECRET` logs everyone
  out.
- **Run it at a console as your own user.** It may ask for your `sudo` password
  when it checks whether the database role exists.
- `--dry-run` prints the file it would write, with secrets redacted, and changes
  nothing.

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

All three must be true and the length must read 64.

### The settings in the file

- `DATABASE_URL` — required. Points at the private cluster on **9431**, and the
  second database (`workbench_data`) is derived from it by changing the database
  name.
- `ENCRYPTION_KEY` — required, and must be exactly 64 hexadecimal characters. It
  encrypts stored connection passwords; if it changes, previously saved
  credentials can no longer be decrypted.
- `NEXTAUTH_SECRET` — signs the session token. Read by both halves.
- `NEXTAUTH_URL` — the address the frontend is served on.
- `ALLOWED_ORIGINS` — the origins allowed to call the API from a browser.

Two settings are deliberately **not** written:

- **`ENVIRONMENT`** — controls whether the backend also writes
  `logs/backend.log` (rotated at 10 MB, three backups) alongside its normal
  output. `development` is the default, so the file log is on unless you set it.
  Set it only to turn that off:

  ```bash
  ENVIRONMENT=production   # stderr only, no log file
  ```

- **`BACKEND_URL`** — the frontend's server-side code defaults to
  `http://127.0.0.1:8000`, which is correct whenever the backend is on the same
  machine. Set it only if your backend runs elsewhere.

> **Edit `config/workbench.env`, never the two links.** An editor that saves by
> renaming replaces a link with a copy of the file, and the two then drift apart
> with nothing reporting it. Re-running the generator repairs the links.

---

## 6. Create the schema

`db/baseline/0000_baseline.sql` is a schema-only dump: every table, column,
index, constraint and sequence the application expects. It is the only file you
apply.

```bash
cd ~/statisticians-workbench
export PGPASSWORD='change-this-password'
export PGHOST=127.0.0.1 PGPORT=9431 PGUSER=workbench PGDATABASE=workbench
```

**Confirm the target before applying anything** — expect `workbench|9431`:

```bash
psql -tAc 'SELECT current_database(), inet_server_port();'
```

Then:

```bash
psql -v ON_ERROR_STOP=1 -f db/baseline/0000_baseline.sql
```

**Check:** the command exits 0 and prints no `ERROR:` lines. Then:

```bash
psql -c '\dt' | wc -l
psql -c '\d "GlobalSettings"' | grep registrationMode
psql -c '\d "UserDataset"' | grep materialize
```

The first prints **35**: 30 tables plus `psql`'s own header, footer and a blank
line. For the table count itself:

```bash
psql -tAc "SELECT count(*) FROM pg_tables WHERE schemaname='public';"
```

which prints **30**. The other two checks confirm the schema is current — they
look for `registrationMode`, and for `materializedAt` and `materializeError`.

### About `db/migrations/`

The numbered files in `db/migrations/` are the history of how the schema reached
its present shape. **They are not applied during an installation**, and they
cannot be: the earliest ones create tables the baseline already contains. The
baseline is the schema; `db/migrations/` is the record of how it got there.

---

## 7. Seed the database

The schema is empty. The application needs a first settings row and an
administrator account before it can be used — without the settings row,
registration fails.

```bash
cd ~/statisticians-workbench
backend/venv/bin/python scripts/workbench-seed.py
```

It reads the database connection from the configuration, runs in a single
transaction, and is safe to run more than once: a second run changes nothing.

It creates:

- the single settings row, with the welcome message
- 100 user groups, `00` (Default) through `99`
- two accounts — `admin@example.com` (administrator) and
  `exampleuser@example.com`
- four AI providers — DeepSeek, OpenRouter, and Ollama local and remote
- the ten built-in visualization types

**Check:**

```bash
psql -c 'SELECT id, "registrationMode", "passwordPolicy", "emailSender", "publicUrl" FROM "GlobalSettings";'
psql -c 'SELECT count(*) FROM "UserGroup";'
psql -c 'SELECT email, "isAdmin" FROM "User" ORDER BY email;'
psql -c 'SELECT code FROM "AIProvider" ORDER BY code;'
psql -c 'SELECT count(*) FROM "VisualizationType";'
```

Expect one settings row with `registrationMode` 0; **100** groups; two users,
with `admin@example.com` marked as an administrator; four providers; **10**
visualization types.

The seeded passwords are `admin123` for the administrator and `User1234#` for
the example user. **Change the administrator password at first login** — it is
published here and in the seed script.

---

## 8. Start the backend

```bash
cd ~/statisticians-workbench
./scripts/start-backend.sh
```

The script activates the Python environment, loads the configuration, and starts
the API server on port 8000. A normal start prints:

```
Uvicorn running on http://0.0.0.0:8000
Started reloader process [...] using WatchFiles
Started server process [...]
No licence file found at .../backend/licence.json — running in open-source mode
Features enabled: access_db, mssql_db, mysql_db, postgres_db
Workbench database cluster: 127.0.0.1:9431 (database 'workbench')
Database pool initialized.
Data database pool initialized (workbench_data).
Application startup complete.
```

The licence line is expected: this edition has no licence file, and the
application falls back to the open-source feature set — the four database
drivers it lists.

Leave this terminal running. The same lines are written to `logs/backend.log` in
the repository root, with timestamps.

**Check** — in a second terminal:

```bash
curl -s http://localhost:8000/api/health
```

Expect:

```json
{"status":"healthy","version":"0.12.2","backend":"python",
 "database":{"pool_initialized":true,"host":"127.0.0.1","port":9431}}
```

`"backend":"python"` confirms which backend answered; `pool_initialized:true`
confirms the database connection; the port confirms it is the private cluster.

Then confirm it can read the data, which the health check does not prove:

```bash
curl -s http://localhost:8000/api/public-settings
```

This returns the settings row you seeded in step 7 — `registrationMode`,
`passwordPolicy`, `demoMode` and the welcome text.

---

## 9. Build and start the frontend

```bash
cd ~/statisticians-workbench/frontend
pnpm install
pnpm build
pnpm start
```

`pnpm install` downloads around 1,200 packages and takes several minutes on a
cold cache; it prints warnings about engine versions on some dependencies, which
are harmless. If it reports that build scripts were blocked, run
`pnpm approve-builds`, select all packages, and re-run.

> **If `node_modules` was ever installed under an older Node, delete it and
> install again.** Several dependencies ship platform-specific native binaries as
> *optional* dependencies, and each declares its own minimum Node version. Under a
> Node below that minimum, `pnpm` skips them — **silently**, because they are
> optional — and reports a successful install. The packages are then missing, and
> the build fails much later with a message that points away from the cause:
>
> ```
> ./app/globals.css
> Error: Cannot find module '@tailwindcss/oxide-linux-x64-gnu'
> ```
>
> The fix is to remove the tree and reinstall, which costs a couple of minutes
> because the package store already holds the downloaded packages:
>
> ```bash
> rm -rf node_modules
> pnpm install
> ```
>
> `pnpm install` alone will **not** repair it: with the lockfile satisfied it
> reports `Already up to date` in seconds and relinks nothing. So install the
> correct Node version (step 1) *before* the first `pnpm install`, and if you
> change Node later, clear `node_modules` afterwards.

`pnpm build` compiles the production build. This project does not use a dev
server — the build is also the check that the frontend is sound.

`pnpm start` serves that build on port 3000.

**Check:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/
```

Expect **307** — the redirect to the login page for an unauthenticated request.
Then open `http://localhost:3000` in a browser: the login page should appear.

---

## 10. Sign in

1. Open `http://localhost:3000/login` and sign in as `admin@example.com` with
   the password `admin123`.
2. **Change that password immediately**, from the profile page or the admin user
   page.
3. Set a real email address for the administrator and verify it, so password
   reset and notification email have somewhere to go.

**Check:** the sidebar shows the admin entries (`/admin/users`,
`/admin/setup/options`), and `/admin/users` lists both seeded accounts.

---

## 11. Verify the installation

Run these after a fresh install. Set the database connection first — it reads
the password out of the configuration rather than asking you to retype it:

```bash
cd ~/statisticians-workbench
PW=$(sed -n 's|^DATABASE_URL=postgresql://[^:]*:\([^@]*\)@.*|\1|p' config/workbench.env)
export PGPASSWORD="$PW" PGHOST=127.0.0.1 PGPORT=9431 PGUSER=workbench PGDATABASE=workbench
```

```bash
# the API is up, and which backend answered
curl -s http://localhost:8000/api/health

# the API can read the database
curl -s http://localhost:8000/api/public-settings

# the frontend is up (307 = the login redirect)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/

# the schema is present
psql -tAc "SELECT count(*) FROM pg_tables WHERE schemaname='public';"

# the seed landed
psql -tAc 'SELECT (SELECT count(*) FROM "UserGroup"), (SELECT count(*) FROM "User"),
                  (SELECT count(*) FROM "AIProvider"), (SELECT count(*) FROM "VisualizationType");'

# an administrator exists
psql -tAc 'SELECT email FROM "User" WHERE "isAdmin" = true;'
```

Expect 30 tables, `100|2|4|10`, and `admin@example.com`. Then sign in and open
a page that needs administrator rights, and confirm no error appears.

---

## 12. Starting over

### Reset the data, keeping the cluster

```bash
sudo -u postgres psql -p 9431 <<'SQL'
DROP DATABASE IF EXISTS workbench_data;
DROP DATABASE IF EXISTS workbench;
DROP ROLE IF EXISTS workbench;
SQL
```

Then repeat from step 3b. The Python environment and `node_modules` do not need
rebuilding unless `requirements.txt` or `package.json` changed.

### Remove the cluster entirely

Only when abandoning the installation. The cluster name in the command is what
protects everything else — it names this cluster specifically, so the machine's
default cluster and every database in it are untouched.

```bash
pg_lsclusters                                    # confirm 16/workbench on 9431
sudo pg_dropcluster --stop 16 workbench
pg_lsclusters                                    # gone; 16/main still online
```

Then delete `config/workbench.env`, or the `DATABASE_URL` line within it.

> **Do not remove PostgreSQL itself to tidy up.** `apt-get purge postgresql-*`
> removes the distribution's package and the default cluster with it, taking any
> database that is not this application's.

---

## Notes

- **This edition is Linux only.** The open source repository is scoped to Linux;
  Windows and macOS are served by the commercial product.
- **The interface is English only** until the translation files are shipped.
- **The frontend must be rebuilt** after a change to `frontend/`, and the server
  restarted — a running process serves the build it started with. The backend
  reloads itself when its source changes.
