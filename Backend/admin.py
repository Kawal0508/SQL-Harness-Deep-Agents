"""Admin service. The only write path to the database. Port 8001.

    cd Backend && uvicorn admin:app --reload --port 8001

Serves Frontend/admin.html. Writes Database/Synthea/health.db and knowledge/.

Deliberately a second process. The agent service opens the database with
`mode=ro` and an authorizer that denies everything but reads; this one opens it
for writing. Keeping them apart means a bug in the agent path cannot reach a
write connection, because there is no write connection in that process to
reach.

`tools.py` has no write-capable connect function at all - not behind a flag,
not behind an environment variable, absent. This file does not import from
`api.py` and `api.py` does not import from here.

Two rules hold the separation up:

1. Every table name here comes from an operator's form field. None of it comes
   from model output, and this file makes no LLM call.
2. Deployment runs this as an OS user with write permission on health.db and
   the agent service as one without. That is the third read-only layer named
   in tools.py, and it is the only one that survives a bug in the other two.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from paths import DB_PATH, TABLES as KNOWLEDGE, table_notes_path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "Frontend"

# Table names are interpolated into DDL, which cannot be parameterised. So the
# name is not escaped, it is refused unless it is a bare identifier.
SAFE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")

app = FastAPI(title="Health data admin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _checked(name: str) -> str:
    if not SAFE_NAME.match(name):
        raise HTTPException(400, "Table name must be letters, digits and underscores.")
    if name.lower().startswith("sqlite_"):
        raise HTTPException(400, "Reserved prefix.")
    return name


@app.get("/tables")
def tables() -> dict:
    conn = _connect()
    try:
        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            "tables": [
                {
                    "name": name,
                    "rows": conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0],
                    "has_notes": table_notes_path(name).is_file(),
                }
                for name in names
            ]
        }
    finally:
        conn.close()


@app.post("/tables")
async def create_table(name: str = Form(...), file: UploadFile = Form(...)) -> dict:
    """Create a table from an uploaded CSV. Header row becomes the columns.

    Every column is TEXT. Synthea's own data is stored that way and it keeps
    leading zeros in codes, which a numeric column silently destroys.
    """
    name = _checked(name)
    raw = (await file.read()).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(raw)))
    if len(rows) < 2:
        raise HTTPException(400, "CSV needs a header row and at least one data row.")

    header = [_checked(c.strip()) for c in rows[0]]
    conn = _connect()
    try:
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone():
            raise HTTPException(409, f"Table '{name}' already exists. Drop it first.")

        columns = ", ".join(f'"{c}" TEXT' for c in header)
        placeholders = ", ".join("?" * len(header))
        with conn:
            conn.execute(f'CREATE TABLE "{name}" ({columns})')
            conn.executemany(
                f'INSERT INTO "{name}" VALUES ({placeholders})',
                # Short rows would raise; pad them so one ragged line does not
                # reject an otherwise good file.
                [(r + [None] * len(header))[: len(header)] for r in rows[1:]],
            )
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    finally:
        conn.close()
    return {"table": name, "rows": count, "columns": header}


@app.delete("/tables/{name}")
def drop_table(name: str, confirm: str = "") -> dict:
    """Drop a table. `confirm` must repeat the table name.

    Typing the name is the whole safeguard. This is irreversible and there is
    no backup of health.db in the repository - it is gitignored and rebuilt
    from Synthea.
    """
    name = _checked(name)
    if confirm != name:
        raise HTTPException(400, f"Pass confirm={name} to drop it.")
    conn = _connect()
    try:
        with conn:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    finally:
        conn.close()
    # Take the notes with it. Left behind, they would silently attach to the
    # next table created under the same name and describe something else.
    (KNOWLEDGE / f"{name}.md").unlink(missing_ok=True)
    return {"dropped": name}


@app.get("/knowledge/{name}")
def read_notes(name: str) -> dict:
    path = table_notes_path(_checked(name))
    return {"table": name, "notes": path.read_text(encoding="utf-8") if path.is_file() else ""}


@app.put("/knowledge/{name}")
def write_notes(name: str, notes: str = Form(...)) -> dict:
    """Write one table's notes.

    The first line is the summary shown in the agent's table index, so it
    should say what the table holds in one line. Everything after it is read
    only when the agent asks about that table specifically.
    """
    path = KNOWLEDGE / f"{_checked(name)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.strip() + "\n", encoding="utf-8")
    return {"table": name, "bytes": len(notes)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "admin.html")
