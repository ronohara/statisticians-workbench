"""The catalogue questions, asked of the session rather than of a schema name.

**Why this module exists.**  A `-ng` endpoint materialises each mounted Access file
into a schema of its own (`accdb_<hash>`) and puts that schema first on the
connection's `search_path`.  A session that names a file therefore has the file's
relations addressable by bare name, with `public` kept behind them.  A query that says
`table_schema = 'public'` asks a *different* question, and against a mounted file it
gets the wrong answer: the tables are not in `public`, so discovery reports an empty
database while the file sits there fully materialised.  That is the bug this module
removes from every call site.

**`pg_class`, and one trap that comes with it.**  `information_schema.tables` hides objects
the current role holds no privilege on, which is why `workbench-go/internal/bikestore/import.go`
reads `pg_class` instead — but `pg_table_is_visible` is **true for `pg_catalog`**, because
PostgreSQL searches `pg_catalog` implicitly ahead of the explicit search path.  Measured
against the live endpoint on 2026-10-06: without the schema exclusion the query returned the
mounted file's seven relations followed by every relation in `pg_catalog`.  So the system
schemas are excluded explicitly, in the idiom this codebase already uses elsewhere
(`routers/dbdesign/schema.go:201`, `rag_query.go:191`).  `pg_toast` needs no exclusion — it is
not on the search path, so nothing in it is visible.

**`current_schema()` would be the smaller edit, and is not equivalent.**  It names the schema
new objects would be created in — the first existing entry of the search path — so a relation
that resolves through a later entry is one the client can use and this query would miss.

**Both placeholder styles** are supported because the call sites use two drivers —
asyncpg (`$1`) and psycopg2 (`%s`) — and the SQL is otherwise identical.  The
placeholder is a parameter of [`columns_of_visible_relation`] so that one copy of the
query serves both; two hand-kept copies would drift, which is a defect this codebase has
paid for before.

**Scope.**  Views count, alongside tables.  The API's own message says "No tables or
views discovered", and a relation the session can name is one the client can use.
The relation's kind travels with its name so that any path offering a *write* can still
tell the two apart — a view is not updatable in general.
"""

#: Every relation this session can name unqualified, with its schema and its kind.
#: Takes no parameters; the caller filters by `table_type` if it wants one kind only.
VISIBLE_RELATIONS = """\
SELECT n.nspname AS table_schema,
       c.relname AS table_name,
       CASE c.relkind
           WHEN 'r' THEN 'BASE TABLE'
           WHEN 'p' THEN 'BASE TABLE'
           WHEN 'v' THEN 'VIEW'
           WHEN 'm' THEN 'MATERIALIZED VIEW'
           WHEN 'f' THEN 'FOREIGN TABLE'
       END AS table_type
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
   AND pg_table_is_visible(c.oid)
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
 ORDER BY n.nspname, c.relname
"""


def relation_kind(table_type: str) -> str:
    """The API's `type` for one `table_type` from [`VISIBLE_RELATIONS`].

    One mapping in one place: the listing endpoints report `"table"` or `"view"`, and
    eight call sites should not each decide that for themselves.
    """
    return "view" if table_type == "VIEW" else "table"


def columns_of_visible_relation(placeholder: str) -> str:
    """Columns of a relation named unqualified, for the driver's `placeholder`.

    `placeholder` is a parameter marker the caller's driver understands — `$1` for
    asyncpg, `%s` for psycopg2 — and the caller binds the table name to it **once**:
    the query uses it a single time and matches the schema by correlation, so an
    existing call site keeps its own parameter shape unchanged.

    `information_schema.columns` is kept rather than a `pg_attribute` query so that the
    `data_type` values the API returns do not change spelling.
    """
    return (
        "SELECT col.column_name, col.data_type, col.is_nullable\n"
        "  FROM information_schema.columns col\n"
        f" WHERE col.table_name = {placeholder}\n"
        "   AND EXISTS (\n"
        "           SELECT 1\n"
        "             FROM pg_class c\n"
        "             JOIN pg_namespace n ON n.oid = c.relnamespace\n"
        "            WHERE c.relname = col.table_name\n"
        "              AND n.nspname = col.table_schema\n"
        "              AND c.relkind IN ('r', 'p', 'v', 'm', 'f')\n"
        "              AND pg_table_is_visible(c.oid)\n"
        "              AND n.nspname NOT IN ('pg_catalog', 'information_schema'))\n"
        " ORDER BY col.ordinal_position"
    )
