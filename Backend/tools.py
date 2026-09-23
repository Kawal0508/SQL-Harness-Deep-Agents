"""Read-only access to the active dataset's SQLite database.

Plain functions, no agent framework imported, so the same file works under any
harness. Every query the agent runs goes through `run_sql`, which is where the
read-only guarantees live.

Read-only enforcement, three independent layers:

1. Connection  - opened with the SQLite `mode=ro` URI flag.
2. Authorizer  - SQLite's own callback rejects every operation that is not a
                 read, at the engine level, before a statement executes. This
                 catches anything a parser would miss.
3. Process     - deploy the agent as an OS user with no write permission on the
                 database file. Not code; see the deployment notes.

`sqlite3.Cursor.execute` refuses more than one statement per call, so stacked
queries ("SELECT 1; DROP TABLE x") are rejected without extra work.

Both public functions return strings and never raise for a bad query: Deep
Agents passes the return value straight to the model, and a message it can read
lets it correct itself where an exception would just end the turn.

The docstrings on `run_sql` and `describe_schema` are the tool descriptions the
model sees - Deep Agents derives the tool name from `__name__`, the description
from the docstring and the argument schema from the type hints. Edit them as
prompt text, not as notes to a maintainer.

Run `python tools.py` to execute the self-check.
"""

from __future__ import annotations

import json
import sqlite3
import time
from functools import lru_cache
from importlib import import_module

from paths import DB_PATH, LAYOUT, table_notes_path

DEFAULT_ROW_LIMIT = 1000
QUERY_TIMEOUT_SECONDS = 30


def _load_profile():
    name = LAYOUT.get("profile")
    if not name:
        return None
    return import_module(name)


_PROFILE = _load_profile()
EDGES: dict = getattr(_PROFILE, "EDGES", {})


def _edge_targets(spec) -> list[tuple[str, str]]:
    if not spec:
        return []
    if isinstance(spec, tuple) and len(spec) == 2 and isinstance(spec[0], str):
        return [spec]
    return list(spec)

# SQLite actions a question-answering agent legitimately needs. Everything else
# - INSERT, UPDATE, DELETE, ATTACH, PRAGMA, CREATE, DROP - is denied.
ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)


class QueryRejected(Exception):
    """A query was refused before or during execution."""


def _authorizer(action: int, *_args: object) -> int:
    return sqlite3.SQLITE_OK if action in ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _connect(restricted: bool = True) -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No database at {DB_PATH}.")
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    if restricted:
        conn.set_authorizer(_authorizer)
    return conn


def _deadline_handler(deadline: float):
    """Progress handler that aborts the query once the deadline passes."""
    return lambda: 1 if time.monotonic() > deadline else 0


def _table_names(conn: sqlite3.Connection) -> list[str]:
    return [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


@lru_cache(maxsize=1)
def _row_counts(_mtime: float) -> dict[str, int]:
    """Row count for every table, cached until the database file changes.

    Keyed on mtime so a table created or dropped by the admin service, which
    runs as its own process, invalidates this without any message passing.

    Worth caching: a large unindexed table (Synthea's claims_transactions is
    2.2M rows) takes seconds to count. Counting every table on every schema
    view was the slowest thing in the app.
    """
    conn = _connect(restricted=False)
    try:
        return {
            name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in _table_names(conn)
        }
    finally:
        conn.close()


def counts() -> dict[str, int]:
    return _row_counts(DB_PATH.stat().st_mtime)


def _knowledge(table: str) -> str:
    """One table's written notes, or empty if nobody has written them yet.

    Files are authored by a human through the admin service. The agent reads
    them and never writes them.
    """
    path = table_notes_path(table)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _summary(table: str) -> str:
    """First line of a table's notes. That line is the one-line summary."""
    return _knowledge(table).split("\n", 1)[0].strip()


def _explain(exc: sqlite3.DatabaseError) -> str:
    message = str(exc)
    if "not authorized" in message or "readonly" in message:
        return "Read-only database. Only SELECT queries are permitted."
    if "one statement at a time" in message:
        return "Send one statement per query."
    if "interrupted" in message:
        return f"Query exceeded {QUERY_TIMEOUT_SECONDS}s. Narrow it and retry."
    return f"SQL error: {message}"


def run_sql(query: str, limit: int = DEFAULT_ROW_LIMIT) -> str:
    """Run one read-only SELECT against the health database and return its rows.

    Only SELECT is permitted; any write, DDL or PRAGMA is refused. Send one
    statement per call. Call describe_schema first and use the column names it
    gives you - do not guess them.

    Args:
        query: A single SELECT statement.
        limit: Maximum rows to return. Defaults to 1000.

    Returns:
        The SQL that ran, the column names, the rows as JSON, the row count, and
        a note if the result was truncated at the limit. On a rejected or
        malformed query, an explanation of what was wrong.
    """
    try:
        conn = _connect()
    except FileNotFoundError as exc:
        return str(exc)
    conn.set_progress_handler(
        _deadline_handler(time.monotonic() + QUERY_TIMEOUT_SECONDS), 10_000
    )
    try:
        cursor = conn.execute(query)
        rows = cursor.fetchmany(limit + 1)
        columns = [d[0] for d in cursor.description] if cursor.description else []
    except sqlite3.DatabaseError as exc:
        return _explain(exc)
    finally:
        conn.close()

    truncated = len(rows) > limit
    rows = [dict(r) for r in rows[:limit]]
    report = [
        f"sql: {query}",
        f"columns: {', '.join(columns) if columns else '(none)'}",
        f"row_count: {len(rows)}",
    ]
    if truncated:
        report.append(f"TRUNCATED at limit {limit}; narrow the query or aggregate.")
    report.append(f"rows: {json.dumps(rows, default=str)}")
    return "\n".join(report)


def describe_schema(table: str | None = None) -> str:
    """Describe the health database so you can write a correct query.

    Call this with no argument first. You get every table, its size, and one
    line on what it holds. Then call it again naming the tables that line says
    are relevant, and you get their columns, indexes, joins, and written notes.
    The notes carry traps that the column names do not show, so read them
    before writing SQL against a table you have not used yet.

    Args:
        table: A table name for its full detail. Omit for the index.

    Returns:
        The table index, or one table's columns, indexed columns, joins and
        notes. If the name is not a table, a list of close matches.
    """
    try:
        conn = _connect(restricted=False)  # PRAGMA needs the authorizer off
    except FileNotFoundError as exc:
        return str(exc)
    try:
        names = _table_names(conn)
        sizes = counts()

        # No argument: the index. Table, size, and one line on what it holds,
        # so the next call can go straight to the right table instead of
        # describing several to find out.
        if table is None:
            lines = ["Tables in this database:", ""]
            for name in names:
                summary = _summary(name)
                lines.append(
                    f"  {name:<22} {sizes[name]:>10,} rows"
                    + (f"  {summary}" if summary else "")
                )
            lines += ["", "Call describe_schema('<table>') for columns and notes."]
            return "\n".join(lines)

        if table not in names:
            close = [n for n in names if table.lower() in n.lower()]
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            return f"No table named '{table}'.{hint} Call describe_schema() for the list."

        lines = [f"# {table} ({sizes[table]:,} rows)", "", "## Columns", ""]
        for row in conn.execute(f'PRAGMA table_info("{table}")'):
            lines.append(f"  {row['name']:<24} {row['type'] or '(untyped)'}")

        indexed = sorted(
            {
                info["name"]
                for index in conn.execute(f'PRAGMA index_list("{table}")')
                for info in conn.execute(f'PRAGMA index_info("{index["name"]}")')
            }
        )
        # Say so when there is no index. On the larger tables an unindexed
        # filter scans every row and hits the 30s timeout.
        lines += ["", f"Indexed columns: {', '.join(indexed) if indexed else 'none'}"]

        joins = EDGES.get(table, {})
        if joins:
            lines += ["", "## Joins", ""]
            for col, spec in sorted(joins.items()):
                for target, key in _edge_targets(spec):
                    lines.append(f"  {col} -> {target}.{key}")

        notes = _knowledge(table)
        if notes:
            lines += ["", "## Notes", "", notes]
        return "\n".join(lines)
    finally:
        conn.close()


def schema_json() -> dict:
    """The whole schema as data, for the browser's map view.

    Not a tool. The model never sees this; describe_schema is its route in.
    """
    conn = _connect(restricted=False)  # PRAGMA needs the authorizer off
    try:
        sizes = counts()
        tables = [
            {
                "name": name,
                "rows": sizes[name],
                "summary": _summary(name),
                "columns": [
                    {"name": row["name"], "type": row["type"] or ""}
                    for row in conn.execute(f'PRAGMA table_info("{name}")')
                ],
            }
            for name in _table_names(conn)
        ]
    finally:
        conn.close()

    edges = [
        {"source": table, "column": col, "target": target, "key": key}
        for table, joins in EDGES.items()
        for col, spec in joins.items()
        for target, key in _edge_targets(spec)
    ]
    return {"tables": tables, "edges": edges}


def _self_check() -> None:
    assert "No table named" in describe_schema("patientz")

    for statement in (
        "CREATE TABLE t (a int)",
        "ATTACH DATABASE 'other.db' AS other",
        "SELECT 1; DROP TABLE t",
    ):
        refusal = run_sql(statement)
        assert "rows:" not in refusal, f"{statement!r} was not refused: {refusal}"

    assert "SQL error" in run_sql("SELECT * FROM no_such_table")

    check = getattr(_PROFILE, "self_check", None) if _PROFILE else None
    if check:
        check(describe_schema, run_sql)
    print("self-check passed")


if __name__ == "__main__":
    _self_check()
