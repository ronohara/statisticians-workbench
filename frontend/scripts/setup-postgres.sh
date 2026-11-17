#!/bin/bash
set -e

# Load .env file if it exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Parse DATABASE_URL to extract components
if [[ -z "$DATABASE_URL" ]]; then
  echo "ERROR: DATABASE_URL is not set in .env file"
  exit 1
fi

URL="$DATABASE_URL"
PROTOCOL="postgresql://"
TEMP="${URL#$PROTOCOL}"
USERPASS="${TEMP%%@*}"
USER="${USERPASS%%:*}"
PASS="${USERPASS#*:}"
REMAINING="${TEMP#*@}"
HOSTPORT="${REMAINING%%/*}"
HOST="${HOSTPORT%:*}"
PORT="${HOSTPORT#*:}"
DBNAME="${REMAINING#*/}"

DB_NAME="${DBNAME:-workbench}"
PGUSER="${USER:-postgres}"
PGPASSWORD="$PASS"
PGHOST="${HOST:-localhost}"
PGPORT="${PORT:-5432}"

export PGUSER PGPASSWORD PGHOST PGPORT

YES_FLAG=0
for arg in "$@"; do
  if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
    YES_FLAG=1
  fi
done

echo "=== Setting up PostgreSQL database '$DB_NAME' ==="

# Check if database exists and create if needed
if psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
  echo "Database '$DB_NAME' already exists."
  if [ $YES_FLAG -eq 0 ]; then
    read -p "Do you want to drop and recreate it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Keeping existing database. Proceeding with migrations..."
    else
      dropdb --if-exists "$DB_NAME"
      createdb "$DB_NAME"
      echo "Database '$DB_NAME' recreated."
    fi
  else
    echo "Non‑interactive mode: dropping and recreating database."
    dropdb --if-exists "$DB_NAME"
    createdb "$DB_NAME"
  fi
else
  createdb "$DB_NAME"
  echo "Database '$DB_NAME' created."
fi


echo "✅ PostgreSQL setup complete."