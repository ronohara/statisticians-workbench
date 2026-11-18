#!/usr/bin/env bash
# generate-env-files.sh — create config/workbench.env and point both halves at it.
#
#   ./scripts/generate-env-files.sh [--force] [--dry-run] [--rotate-db-password]
#
# One file, two symlinks:
#
#   config/workbench.env        the configuration, mode 600, gitignored
#   backend/.env   -> ../config/workbench.env
#   frontend/.env  -> ../config/workbench.env
#
# That is the same shape the .deb installs at /etc/workbench/workbench.env,
# where one file is shared by both systemd units. Each half still loads `.env`
# from the directory it already looks in — python-dotenv for the backend, Next
# for the frontend — so neither application needs to know about symlinks.
#
# What it is for: NEXTAUTH_SECRET and ENCRYPTION_KEY must be the same value in
# both halves. Two files made that a convention that had to hold; one file makes
# it a fact.
#
# Revision of workbench-development/scripts/generate-env-files.sh, which was
# withdrawn to a refusal stub (commit 4c2b2bb). Read that stub's header before
# changing this one: it lists four things the old script did that this one must
# not. Each is addressed below.
#
#   1. It targeted port 5432 with an administrator credential (PG_ADMIN_PASS,
#      defaulting to a password in the source). This installs against the
#      PRIVATE cluster on 9431 and never asks for, stores or prints an
#      administrator password.
#
#   2. It ran ALTER ROLE workbench WITH PASSWORD on every invocation. A running
#      backend keeps the old password in memory, so the next restart fails to
#      authenticate — a breakage that appears hours after the script that caused
#      it. This script never rotates a password unless --rotate-db-password is
#      given, and it refuses outright when the role already exists and it cannot
#      know the password.
#
#   3. It created a Linux user 'workbench' with useradd, set its password with
#      chpasswd, and chown -R'd the ENTIRE CHECKOUT to it. Nothing here does
#      that. The tree stays owned by whoever cloned it.
#
#   4. It prompted with read -p, so it could not run unattended. This one takes
#      no input: it prints what it will do, and --force is the consent to
#      overwrite.
#
# What it writes
# --------------
#   config/workbench.env   DATABASE_URL, NEXTAUTH_URL, NEXTAUTH_SECRET,
#                          ENCRYPTION_KEY, ALLOWED_ORIGINS — the same five the
#                          .deb installs, so the two arrangements agree.
#
# `ENVIRONMENT` is deliberately NOT written. It is real — main.py:105 and
# Logger.__init__ read it — but "development" is its default on both sides, so
# writing `ENVIRONMENT=development` changes nothing while making the file read as
# though the setting mattered here. A variable that restates a default is a line
# someone will later assume is load-bearing. Set it yourself only to leave
# development, which switches the file log off.
#
# Both files are mode 600 — they hold two secrets each — and both are gitignored
# by the repository's `.env*` rule with `!.env.example` carved out.
#
# What it requires
# -----------------
# The private PostgreSQL cluster must already be RUNNING on the port this script
# writes into DATABASE_URL. That is a precondition, not a preference: a .env file
# written while the cluster is down looks correct and fails at step 8 with a
# connection error, long after the schema and the seed have been run. The script
# verifies the cluster with pg_isready and refuses if it does not answer.
#
# Environment overrides (all optional)
# ------------------------------------
#   WORKBENCH_DB_PASSWORD   reuse this password for the workbench role, instead
#                           of generating one. Set it when the role already
#                           exists: this script will not guess.
#   WORKBENCH_DB_HOST       default 127.0.0.1
#   WORKBENCH_DB_PORT       default 9431 — the private cluster
#   WORKBENCH_URL           default http://localhost:3000
#   WORKBENCH_BACKEND_URL   default http://127.0.0.1:8000
#   ALLOWED_ORIGINS         default taken from WORKBENCH_URL
#
# Exit codes
# ----------
#   0  files written (or would be, under --dry-run)
#   1  refused: .env files exist and --force was not given, the role exists and
#      its password is unknown, or the role's existence could not be determined
#      and no password was supplied
#   2  a required tool is missing, or a secret could not be generated
#   3  the private cluster is not running — nothing was written

set -euo pipefail

# --- arguments -------------------------------------------------------------

FORCE=false
DRY_RUN=false
ROTATE=false

usage() {
    sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//' | sed '$d'
}

for arg in "$@"; do
    case "$arg" in
        --force)              FORCE=true ;;
        --dry-run|-n)         DRY_RUN=true ;;
        --rotate-db-password) ROTATE=true ;;
        --help|-h)            usage; exit 0 ;;
        *)
            echo "error: unknown argument '$arg'" >&2
            echo "  try --help" >&2
            exit 2
            ;;
    esac
done

# --- locations -------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKBENCH_DIR="$(dirname "$SCRIPT_DIR")"

# One file, and two symlinks that point at it.
#
# config/workbench.env is the single source of truth — the same shape the .deb
# installs at /etc/workbench/workbench.env, where one file is shared by both
# systemd units. backend/.env and frontend/.env are relative symlinks to it, so
# each half keeps loading `.env` from the directory it already looks in, and
# there is still only one copy of the two secrets to get wrong.
#
# The symlinks are NOT committed: .gitignore's `.env*` rule covers them, which
# is correct for files that hold secrets, so a fresh clone has neither and this
# script creates both.
CONFIG_DIR="$WORKBENCH_DIR/config"
ENV_FILE="$CONFIG_DIR/workbench.env"
BACKEND_ENV="$WORKBENCH_DIR/backend/.env"
FRONTEND_ENV="$WORKBENCH_DIR/frontend/.env"
LINK_TARGET="../config/workbench.env"

for d in "$WORKBENCH_DIR/backend" "$WORKBENCH_DIR/frontend"; do
    if [[ ! -d "$d" ]]; then
        echo "error: $d does not exist — run this from a checkout of the repository" >&2
        exit 2
    fi
done

# --- tools -----------------------------------------------------------------

for tool in openssl psql; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: '$tool' is required and was not found on PATH" >&2
        exit 2
    fi
done

# --- refusal if the config already exists -------------------------------
#
# Two things are checked, because they fail differently and both are silent:
#
#   config/workbench.env        the file itself. Overwriting it rewrites both
#                               secrets, which invalidates every session token
#                               and every stored connection password.
#
#   backend/.env, frontend/.env A REGULAR FILE at either path is a leftover from
#                               the older two-file arrangement. It looks like
#                               the right thing, is read by the app, and would
#                               be silently replaced by a symlink — deleting
#                               whatever secrets were in it.
#
# A symlink at either path is not a refusal: that is the arrangement this script
# creates, and pointing it at the right file is the job.

EXISTING=()
[[ -f "$ENV_FILE" ]] && EXISTING+=("$ENV_FILE (the config file)")
for link in "$BACKEND_ENV" "$FRONTEND_ENV"; do
    if [[ -f "$link" && ! -L "$link" ]]; then
        EXISTING+=("$link (a regular file, not a symlink)")
    fi
done

if (( ${#EXISTING[@]} > 0 )) && [[ "$FORCE" != true ]]; then
    echo "Refused: configuration already exists." >&2
    for f in "${EXISTING[@]}"; do echo "  $f" >&2; done
    echo "" >&2
    echo "  This script writes secrets. Overwriting them silently would invalidate" >&2
    echo "  every session token and every stored connection password encrypted with" >&2
    echo "  the old ENCRYPTION_KEY." >&2
    echo "" >&2
    echo "  Re-run with --force to replace it; a timestamped copy of each file is" >&2
    echo "  kept first." >&2
    exit 1
fi

# --- connection settings ---------------------------------------------------

DB_HOST="${WORKBENCH_DB_HOST:-127.0.0.1}"
DB_PORT="${WORKBENCH_DB_PORT:-9431}"
DB_NAME="workbench"
DB_USER="workbench"

WB_URL="${WORKBENCH_URL:-http://localhost:3000}"
BACKEND_URL="${WORKBENCH_BACKEND_URL:-http://127.0.0.1:8000}"

# --- the private cluster must be running ---------------------------------
# A hard precondition, checked before anything is written. pg_isready answers
# about the port and says nothing about whether the schema exists, which is what
# makes it the right test here: step 5 may legitimately run before step 6.
#
# Its exit codes are distinguished because they mean different things and want
# different remedies:
#   0  accepting connections
#   1  rejecting connections — the cluster exists but is starting up or shutting
#      down. Waiting is usually enough; nothing needs creating.
#   2  no response — nothing is listening on that port. The cluster has not been
#      created, or it is stopped, or the port is wrong.
#   3  no attempt made — invalid parameters, which here means a bad host or port.

isready_rc=0
isready_out=$(pg_isready -h "$DB_HOST" -p "$DB_PORT" 2>&1) || isready_rc=$?

case "$isready_rc" in
    0) : ;;
    1) cluster_state="rejecting connections — it exists but is not ready (starting up or shutting down)" ;;
    2) cluster_state="no response — nothing is listening on that port" ;;
    3) cluster_state="the host or port is invalid" ;;
    *) cluster_state="pg_isready exited $isready_rc" ;;
esac

if (( isready_rc != 0 )); then
    cat >&2 <<EOF
error: the private PostgreSQL cluster is not running on ${DB_HOST}:${DB_PORT}.

  pg_isready said: ${cluster_state}
       its output: ${isready_out:-<none>}

  A .env file written while the cluster is down looks correct and fails at step 8
  with a connection error, after the schema and the seed have both been run. So
  nothing has been written.

  Create the cluster (Installing.md step 3), then run this script again:

    sudo pg_createcluster 16 workbench --port 9431 \\
         --locale=en_US.UTF-8 --encoding=UTF8
    sudo systemctl start postgresql@16-workbench
    pg_isready -p 9431

  If the cluster already exists and is merely stopped:

    sudo systemctl start postgresql@16-workbench

  If it lives on another host or port, say so rather than editing this script:

    WORKBENCH_DB_HOST=<host> WORKBENCH_DB_PORT=<port> $0
EOF
    exit 3
fi

# --- does the role exist, and can we learn its password? ------------------
# Peer auth as postgres over the socket, the same route step 3b uses. Non-
# interactive sudo only: a password prompt in the middle of a generator is the
# defect this script exists to avoid.
#
# Three outcomes matter:
#   ROLE=present  the role exists — its password must be supplied, never guessed
#   ROLE=absent   a fresh password will be created, with the SQL to create it
#   ROLE=unknown  the cluster is up but this script could not ask it. That
#                 happens where sudo wants a password (this script only uses
#                 sudo -n) or where the sudoers rule does not allow psql as
#                 postgres. It is reported as unknown rather than guessed.

ROLE=unknown
if command -v sudo >/dev/null 2>&1; then
    # The exit status distinguishes the two cases an empty result would merge:
    # psql exiting 0 with no rows means the role is genuinely absent, while
    # psql failing means the question was never answered. Reading both as
    # "unknown" would make the absent branch unreachable on any machine where
    # the query works; reading both as "absent" would claim a fact nobody checked.
    if role_query=$(sudo -n -u postgres psql -p "$DB_PORT" -tAc \
            "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER';" 2>/dev/null); then
        if [[ "$role_query" == "1" ]]; then ROLE=present; else ROLE=absent; fi
    fi
fi

# --- the database password ------------------------------------------------
if [[ -n "${WORKBENCH_DB_PASSWORD:-}" ]]; then
    DB_PASSWORD="$WORKBENCH_DB_PASSWORD"
    PASSWORD_SOURCE="WORKBENCH_DB_PASSWORD from the environment"
elif [[ "$ROTATE" == true ]]; then
    DB_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
    PASSWORD_SOURCE="newly generated, because --rotate-db-password was given"
elif [[ "$ROLE" == present ]]; then
    echo "Refused: the role '$DB_USER' already exists on $DB_HOST:$DB_PORT," >&2
    echo "and this script does not know its password." >&2
    echo "" >&2
    echo "  A generated password here would be written into .env without being" >&2
    echo "  applied to the role, and the backend would fail at its first query" >&2
    echo "  with 28P01 — long after this script reported success." >&2
    echo "" >&2
    echo "  Choose one:" >&2
    echo "    WORKBENCH_DB_PASSWORD='the-existing-password' $0$([[ "$FORCE" == true ]] && echo ' --force')" >&2
    echo "    $0 --rotate-db-password   # generates a new one and prints the ALTER ROLE to run" >&2
    exit 1
elif [[ "$ROLE" == unknown ]]; then
    echo "Refused: the cluster is running, but this script could not ask it whether" >&2
    echo "the role '$DB_USER' exists." >&2
    echo "" >&2
    echo "  It only uses non-interactive sudo, and that was refused. Without knowing" >&2
    echo "  whether the role is there, a generated password would be written into" >&2
    echo "  .env without any statement that applies it — the 28P01 trap below, with" >&2
    echo "  no way to tell which statement to run." >&2
    echo "" >&2
    echo "  Choose one:" >&2
    echo "    WORKBENCH_DB_PASSWORD='choose-one' $0   # supply it; both SQL forms are printed" >&2
    echo "    sudo -v && $0                          # cache sudo, then this script can ask" >&2
    echo "" >&2
    echo "  The second works because 'sudo -v' caches the credential for the terminal" >&2
    echo "  session; the script's 'sudo -n' then succeeds without ever prompting." >&2
    exit 1
else
    DB_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
    PASSWORD_SOURCE="newly generated"
fi

DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# --- secrets ---------------------------------------------------------------
# ENCRYPTION_KEY must be exactly 64 hexadecimal characters: backend/src/utils/
# encryption.py raises at import time otherwise. NEXTAUTH_SECRET signs the
# session token and is shared by both halves — the frontend mints it and the
# backend verifies it, so the two files must carry the same value.

ENCRYPTION_KEY="$(openssl rand -hex 32)"
NEXTAUTH_SECRET="$(openssl rand -base64 32)"

if [[ ${#ENCRYPTION_KEY} -ne 64 ]]; then
    echo "error: ENCRYPTION_KEY is ${#ENCRYPTION_KEY} characters, not 64" >&2
    exit 2
fi

# --- file contents ---------------------------------------------------------

# One file, five keys — the same five the .deb installs, so the two arrangements
# agree. Each half reads what it needs and ignores the rest; the packaged system
# proves that is harmless, because both units there load the same six keys.
#
# Deliberately absent:
#   BACKEND_URL / NEXT_PUBLIC_BACKEND_URL — both halves default to
#       http://127.0.0.1:8000, and the package sets neither. NEXT_PUBLIC_* is
#       baked into the frontend bundle at BUILD time, so writing it at runtime
#       would not reach the browser anyway.
#   ENVIRONMENT — "development" is its default on both sides, so writing it
#       changes nothing; see the note in the header.
#   LICENCE_FILE — the Python backend falls back to ../licence.json, and a path
#       to a licence that will not exist is configuration for a commercial
#       concern.

ENV_CONTENT="# Workbench runtime configuration — read by both the backend and the frontend.
#
# backend/.env and frontend/.env are symlinks to this file, so there is one copy
# of NEXTAUTH_SECRET and ENCRYPTION_KEY rather than two that have to agree.
# Edit THIS file, never the symlinks: an editor that saves by renaming replaces
# the link with a copy, and the two then drift apart silently. Re-run
# scripts/generate-env-files.sh to repair the links.
#
# gitignored — it holds secrets.

# PostgreSQL connection, on the private cluster (port 9431, never 5432).
DATABASE_URL=${DATABASE_URL}

# NextAuth. NEXTAUTH_URL is where the frontend is served; NEXTAUTH_SECRET signs
# the session token and must be the same value for both halves, which the shared
# file now guarantees.
NEXTAUTH_URL=${WB_URL}
NEXTAUTH_SECRET=${NEXTAUTH_SECRET}

# 32-byte hex key for stored connection passwords. Changing it makes every
# saved credential undecryptable.
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# CORS allow-list, comma-separated origins.
ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-$WB_URL}"

# --- report ----------------------------------------------------------------

echo "Statisticians Workbench — environment files"
echo "════════════════════════════════════════════"
echo "  repository     $WORKBENCH_DIR"
echo "  database       $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo "  cluster        accepting connections on $DB_PORT"
echo "  role           $ROLE"
echo "  password       $PASSWORD_SOURCE"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo "--dry-run: nothing written. The file would contain:"
    echo ""
    # Redact every secret this script owns: the two named ones, and the password
    # inside the DSN. The database password is printed once, deliberately, in the
    # SQL block below — where it is needed — but a file listing is not the place
    # for it, because a dry run is the output someone pipes or pastes.
    redact() {
        sed -E 's/(_KEY=|_SECRET=)[^ ]+/\1<redacted>/; s#(://[^:]+:)[^@]+@#\1<redacted>@#'
    }
    echo "  config/workbench.env"
    sed 's/^/    /' <<<"$ENV_CONTENT" | redact
    echo ""
    echo "  then two symlinks pointing at it:"
    echo "    backend/.env  -> ../config/workbench.env"
    echo "    frontend/.env -> ../config/workbench.env"
    echo ""
fi

# --- the SQL that makes the .env true --------------------------------------
# Printed, never executed. The role and both databases are created over peer
# auth as postgres — the same block Installing.md step 3b carries — so no
# administrator credential passes through this script.

print_create_block() {
    echo "  sudo -u postgres psql -p $DB_PORT <<'SQL'"
    echo "  CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD';"
    echo "  ALTER ROLE $DB_USER NOSUPERUSER NOCREATEDB NOCREATEROLE;"
    echo "  CREATE DATABASE $DB_NAME      OWNER $DB_USER;"
    echo "  CREATE DATABASE ${DB_NAME}_data OWNER $DB_USER;"
    echo "  ALTER DATABASE $DB_NAME      SET timezone = 'UTC';"
    echo "  ALTER DATABASE ${DB_NAME}_data SET timezone = 'UTC';"
    echo "  SQL"
    echo ""
}

print_alter_block() {
    echo "  sudo -u postgres psql -p $DB_PORT -c \\"
    echo "    \"ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASSWORD';\""
    echo ""
}

case "$ROLE" in
    absent)
        echo "The role does not exist yet. Step 3b creates it; run:"
        echo ""
        print_create_block
        ;;
    present)
        if [[ "$ROTATE" == true ]]; then
            echo "Password rotated. Apply it to the existing role:"
            echo ""
            print_alter_block
            echo "  Every running backend keeps the old password in memory: restart them"
            echo "  after this, or the next restart fails to authenticate."
            echo ""
        fi
        ;;
    unknown)
        if [[ "$ROTATE" == true ]]; then
            echo "Password rotated."
            echo ""
        fi
        echo "The cluster is up, but this script could not ask it whether the role"
        echo "exists, so it cannot know which statement applies. Run the one that"
        echo "matches what you find:"
        echo ""
        echo "  If the role is absent:"
        echo ""
        print_create_block
        echo "  If the role is present and you are setting its password:"
        echo ""
        print_alter_block
        ;;
esac

if [[ "$DRY_RUN" == true ]]; then
    echo "--dry-run: stopping before the write."
    exit 0
fi

# --- back up and write -----------------------------------------------------

umask 077

finish_file() {
    local path="$1" content="$2"
    if [[ -f "$path" ]] && [[ "$FORCE" == true ]]; then
        local backup="${path}.bak-$(date +%Y%m%d-%H%M%S)"
        cp -p "$path" "$backup"
        echo "  backed up $path -> $backup"
    fi
    local tmp="${path}.tmp.$$"
    printf '%s\n' "$content" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$path"
    echo "  wrote $path (mode 600)"
}

# NOTE on the write above: `mv` replaces the file the path names, so it destroys
# any symlink at that path. That is fine for $ENV_FILE, which is a regular file
# and must be one. It is NOT fine for the two .env paths, which are links — they
# are created below with `ln -sfn` and never written to directly.

mkdir -p "$CONFIG_DIR"
finish_file "$ENV_FILE" "$ENV_CONTENT"

# --- the two symlinks ------------------------------------------------------
# `ln -sfn` replaces an existing symlink in place. It must never be pointed at a
# regular file — that would delete whatever secrets it held — which is why the
# refusal block above tests `-f` and not just `-L`.

make_link() {
    local link="$1"
    # A regular file here is a leftover from the two-file arrangement. `ln -sfn`
    # would delete it outright, so it is copied out of the way first — the
    # refusal message promises a timestamped copy, and --force is consent to
    # replace, not consent to lose whatever secrets it held.
    if [[ -f "$link" && ! -L "$link" ]]; then
        local backup="${link}.bak-$(date +%Y%m%d-%H%M%S)"
        cp -p "$link" "$backup"
        echo "  backed up $link -> $backup"
    fi
    ln -sfn "$LINK_TARGET" "$link"
    echo "  linked $link -> $LINK_TARGET"
}

make_link "$BACKEND_ENV"
make_link "$FRONTEND_ENV"

# --- assert the arrangement is what was intended --------------------------
# The check the design needs: a symlink that has become a regular file is a
# second copy of the secrets, and nothing else in the system would report it.
# Both halves would keep running, reading a stale copy, and the divergence would
# surface much later as "everyone is logged out" or "saved credentials cannot be
# decrypted" — the failure mode measured on 2026-11-18 with `sed -i` and with any
# editor that saves by renaming.

link_problems=0
for link in "$BACKEND_ENV" "$FRONTEND_ENV"; do
    if [[ -d "$link" && ! -L "$link" ]]; then
        # `ln -sfn` into a directory creates <dir>/basename instead of replacing
        # it, so the link silently lands one level too deep and the app reads
        # nothing. Caught here because nothing else would report it.
        echo "error: $link is a directory; ln created $link/workbench.env instead." >&2
        echo "       Remove the directory first: rm -r '$link'" >&2
        link_problems=$((link_problems + 1))
    elif [[ ! -L "$link" ]]; then
        echo "error: $link is not a symlink — it is a regular file, and the" >&2
        echo "       configuration is now in two places that can drift apart." >&2
        link_problems=$((link_problems + 1))
    elif [[ "$(readlink "$link")" != "$LINK_TARGET" ]]; then
        echo "error: $link points at '$(readlink "$link")', not $LINK_TARGET." >&2
        link_problems=$((link_problems + 1))
    fi
done
if (( link_problems > 0 )); then
    echo "" >&2
    echo "  Repair with:" >&2
    echo "    ln -sfn $LINK_TARGET backend/.env" >&2
    echo "    ln -sfn $LINK_TARGET frontend/.env" >&2
    exit 1
fi
echo "  both links verified"

# --- verify the DSN against the cluster, when it can be --------------------
# The point of this check is the failure it catches: a password written into
# .env that the role does not have. Reporting that here is a one-second answer;
# discovering it at step 8 is a 28P01 in a backend log, after the schema and the
# seed have both been done.

echo ""
case "$ROLE" in
    present)
        if verify_err=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT 1;' 2>&1 >/dev/null); then
            echo "Verified: the credential in config/workbench.env authenticates to $DB_NAME."
        elif [[ "$ROTATE" == true ]]; then
            echo "Not verified yet, and that is expected: the password was rotated a"
            echo "  moment ago and the ALTER ROLE above has not been run. Apply it, then"
            echo "  re-run this script (with --force) and it will confirm the credential."
        else
            # The failure is reported verbatim rather than collapsed into one
            # warning, because three different faults produce three different
            # messages and only one of them is about the password:
            #   28P01  the password does not match the role
            #   3D000  the role is fine, the database has not been created yet
            #   08006  nothing is listening — the cluster went down mid-run
            echo "WARNING: the credential in config/workbench.env did not connect." >&2
            echo "  psql said:" >&2
            printf '%s\n' "${verify_err:-no message}" | sed 's/^/    /' >&2
            echo "  Fix this before step 8: 28P01 is a password mismatch, 3D000 means" >&2
            echo "  step 6 has not run, and a connection failure means the cluster is down." >&2
        fi
        ;;
    absent)
        echo "Not verified: the role does not exist yet. Run the SQL above (step 3b),"
        echo "  then re-run this script and it will check the credential for you."
        ;;
    unknown)
        # The connection attempt is still worth making: it cannot say which fault
        # it is, but a success is conclusive — the role exists and the password
        # matches — and that is the case where proceeding is safe.
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT 1;' >/dev/null 2>&1; then
            echo "Verified: the credential in config/workbench.env authenticates to $DB_NAME."
            echo "  (The role exists after all — the query above simply could not see it.)"
        else
            echo "Not verified: the credential did not connect, and this script could"
            echo "  not tell whether that is a missing role or a different password."
            echo "  Run whichever statement above matches what you find, then re-run"
            echo "  this script to confirm."
        fi
        ;;
esac

echo ""
echo "Next: step 6 applies the schema, step 7 seeds it, step 8 starts the backend."
