#!/usr/bin/env bash
#
# Migrate the farmfills Postgres database from an old server into the
# Coolify-hosted Postgres.
#
# Runs INSIDE the production app container, which can already reach the target
# Postgres over the Docker network -- no exposed port needed:
#
#   ./scripts/migrate_db.sh                 # dry run (default, touches nothing)
#   ./scripts/migrate_db.sh --apply         # actually dump + restore
#   ./scripts/migrate_db.sh --apply --wipe-target
#
# Source settings come from .env.migrate (see .env.migrate.example); the target
# defaults to the app's own DATABASE_* / DATABASE_URL environment.

set -euo pipefail

APPLY=0
WIPE=0
ENV_FILE=".env.migrate"

while [ $# -gt 0 ]; do
    case "$1" in
        --apply)        APPLY=1 ;;
        --wipe-target)  WIPE=1 ;;
        --env-file)     ENV_FILE="$2"; shift ;;
        -h|--help)      sed -n '2,10p' "$0"; exit 0 ;;
        *)              echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------- config

# Source credentials live in .env.migrate; it is only needed for a real run,
# but a dry run without it can't do much either.
if [ -f "./$ENV_FILE" ]; then
    set -a; . "./$ENV_FILE"; set +a
else
    echo "note: $ENV_FILE not found, relying on the environment" >&2
fi

require() {
    for v in "$@"; do
        [ -n "${!v:-}" ] || { echo "$v is not set (see .env.migrate.example)" >&2; exit 1; }
    done
}
require SOURCE_HOST SOURCE_PORT SOURCE_DB SOURCE_USER SOURCE_PASS

# The target is this container's own database. Reuse the app's env so there is
# no second place to keep the new credentials in sync.
if [ -n "${DATABASE_URL:-}" ]; then
    # postgres://user:pass@host:port/name
    _u="${DATABASE_URL#*://}"
    _creds="${_u%%@*}"; _rest="${_u#*@}"
    TARGET_USER="${TARGET_USER:-${_creds%%:*}}"
    TARGET_PASS="${TARGET_PASS:-${_creds#*:}}"
    TARGET_HOST="${TARGET_HOST:-${_rest%%:*}}"
    _hostport="${_rest%%/*}"
    TARGET_PORT="${TARGET_PORT:-${_hostport#*:}}"
    TARGET_DB="${TARGET_DB:-${_rest#*/}}"
    TARGET_DB="${TARGET_DB%%\?*}"
else
    TARGET_HOST="${TARGET_HOST:-${DATABASE_HOST:-}}"
    TARGET_PORT="${TARGET_PORT:-${DATABASE_PORT:-5432}}"
    TARGET_DB="${TARGET_DB:-${DATABASE_NAME:-}}"
    TARGET_USER="${TARGET_USER:-${DATABASE_USER:-}}"
    TARGET_PASS="${TARGET_PASS:-${DATABASE_PASS:-}}"
fi
require TARGET_HOST TARGET_PORT TARGET_DB TARGET_USER TARGET_PASS

for bin in pg_dump pg_restore psql; do
    command -v "$bin" >/dev/null || { echo "$bin not found (install postgresql-client)" >&2; exit 1; }
done

# /tmp inside the container is ephemeral; that is fine, the dump is disposable.
DUMP_FILE="${DUMP_FILE:-/tmp/farmfills-$(date +%Y%m%d-%H%M%S).dump}"

# ---------------------------------------------------------------- helpers

src_psql() {
    PGPASSWORD="$SOURCE_PASS" psql -h "$SOURCE_HOST" -p "$SOURCE_PORT" \
        -U "$SOURCE_USER" -d "$SOURCE_DB" -tAq "$@"
}

tgt_psql() {
    PGPASSWORD="$TARGET_PASS" psql -h "$TARGET_HOST" -p "$TARGET_PORT" \
        -U "$TARGET_USER" -d "$TARGET_DB" -tAq "$@"
}

LIST_TABLES="SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"

# Exact per-table row counts, printed as "table<TAB>count".
row_counts() {
    local runner="$1" tables t
    tables=$($runner -c "$LIST_TABLES")
    for t in $tables; do
        printf '%s\t%s\n' "$t" "$($runner -c "SELECT count(*) FROM \"$t\";")"
    done
}

major_version() {
    "$1" -c "SHOW server_version;" | cut -d. -f1
}

# ---------------------------------------------------------------- checks

echo "=== farmfills db migration ==="
echo "source : $SOURCE_USER@$SOURCE_HOST:$SOURCE_PORT/$SOURCE_DB"
echo "target : $TARGET_USER@$TARGET_HOST:$TARGET_PORT/$TARGET_DB"
echo "dump   : $DUMP_FILE"
echo

echo "-- connectivity"
src_psql -c "SELECT 1;" >/dev/null && echo "   source OK"
tgt_psql -c "SELECT 1;" >/dev/null && echo "   target OK"

SRC_MAJOR=$(major_version src_psql)
TGT_MAJOR=$(major_version tgt_psql)
CLIENT_MAJOR=$(pg_dump --version | grep -oE '[0-9]+' | head -1)
echo "   postgres $SRC_MAJOR -> $TGT_MAJOR (pg_dump client $CLIENT_MAJOR)"
if [ "$SRC_MAJOR" -gt "$TGT_MAJOR" ]; then
    echo "   WARNING: target is older than source; pg_restore may fail." >&2
fi
if [ "$SRC_MAJOR" -gt "$CLIENT_MAJOR" ]; then
    echo "   ERROR: pg_dump $CLIENT_MAJOR cannot dump a Postgres $SRC_MAJOR server." >&2
    echo "          Rebuild the image with a matching postgresql-client-$SRC_MAJOR." >&2
    exit 1
fi
echo

echo "-- source tables"
SRC_COUNTS=$(row_counts src_psql)
echo "$SRC_COUNTS" | awk -F'\t' '{printf "   %-40s %10s\n", $1, $2}'
SRC_TOTAL=$(echo "$SRC_COUNTS" | awk -F'\t' '{s+=$2} END {print s+0}')
SRC_TABLES=$(echo "$SRC_COUNTS" | grep -c . || true)
echo "   ($SRC_TABLES tables, $SRC_TOTAL rows)"
echo

echo "-- target state"
TGT_TABLES=$(tgt_psql -c "$LIST_TABLES" | grep -c . || true)
echo "   $TGT_TABLES existing tables in public schema"
if [ "$TGT_TABLES" -gt 0 ] && [ "$WIPE" -eq 0 ]; then
    echo "   WARNING: target is not empty. pg_restore will hit 'already exists'"
    echo "            errors. Re-run with --wipe-target to drop the public schema"
    echo "            first, or restore into a fresh database."
fi
echo

# ---------------------------------------------------------------- dry run

if [ "$APPLY" -eq 0 ]; then
    echo "-- DRY RUN: nothing was changed. Would run:"
    echo
    echo "   pg_dump -h $SOURCE_HOST -p $SOURCE_PORT -U $SOURCE_USER -d $SOURCE_DB \\"
    echo "       --format=custom --no-owner --no-privileges -f $DUMP_FILE"
    if [ "$WIPE" -eq 1 ]; then
        echo "   psql <target> -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'"
    fi
    echo "   pg_restore <target> --no-owner --no-privileges --jobs=4 $DUMP_FILE"
    echo
    echo "   then compare per-table row counts and report any mismatch."
    echo
    echo "Re-run with --apply to perform the migration."
    exit 0
fi

# ---------------------------------------------------------------- apply

echo "-- APPLY"
if [ "$WIPE" -eq 1 ]; then
    echo "   This will DROP ALL DATA in $TARGET_DB on the target and replace it"
    echo "   with the source database. This cannot be undone."
fi
if [ "${FORCE:-0}" != "1" ]; then
    printf "   Type 'migrate' to continue: "
    read -r reply
    [ "$reply" = "migrate" ] || { echo "   aborted."; exit 1; }
fi

echo "   dumping source..."
PGPASSWORD="$SOURCE_PASS" pg_dump -h "$SOURCE_HOST" -p "$SOURCE_PORT" \
    -U "$SOURCE_USER" -d "$SOURCE_DB" \
    --format=custom --no-owner --no-privileges \
    -f "$DUMP_FILE"
echo "   wrote $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

if [ "$WIPE" -eq 1 ]; then
    echo "   wiping target public schema..."
    tgt_psql -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

echo "   restoring into target..."
PGPASSWORD="$TARGET_PASS" pg_restore -h "$TARGET_HOST" -p "$TARGET_PORT" \
    -U "$TARGET_USER" -d "$TARGET_DB" \
    --no-owner --no-privileges --jobs=4 "$DUMP_FILE"
rm -f "$DUMP_FILE"

# ---------------------------------------------------------------- verify

echo
echo "-- verifying row counts"
TGT_COUNTS=$(row_counts tgt_psql)

MISMATCH=0
while IFS=$'\t' read -r table count; do
    [ -n "$table" ] || continue
    tgt=$(echo "$TGT_COUNTS" | awk -F'\t' -v t="$table" '$1==t {print $2}')
    if [ -z "$tgt" ]; then
        printf "   MISSING  %-40s source=%s target=-\n" "$table" "$count"
        MISMATCH=1
    elif [ "$tgt" != "$count" ]; then
        printf "   DIFF     %-40s source=%s target=%s\n" "$table" "$count" "$tgt"
        MISMATCH=1
    fi
done <<< "$SRC_COUNTS"

if [ "$MISMATCH" -eq 1 ]; then
    echo
    echo "   FAILED: row counts do not match. Do not point DNS at the new app." >&2
    exit 1
fi

echo "   all $SRC_TABLES tables match ($SRC_TOTAL rows)."
echo
echo "Done. Next: deploy the app and confirm 'migrate' reports no pending migrations."
