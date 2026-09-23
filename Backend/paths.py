"""Filesystem layout for the active dataset.

Every path is derived here. Switch datasets with `DATASET` (a directory
under `Database/`, default `Synthea`). Nested names work:
`DATASET=CMS_SynPUF/sample1`.

Knowledge filenames are not global. Each dataset may ship `layout.json`:

    {
      "definitions": [
        "knowledge/instructions.md",
        "knowledge/definitions.md"
      ],
      "tables": "knowledge/tables/{table}.md"
    }

`definitions` is a list of files always loaded into the system prompt, in
order. Put tool-order instructions first, then cohort rules. `tables` is a
path relative to the dataset root; `{table}` is the SQL table name. If that
file is missing, `knowledge/tables/{table}.md` is still tried so the admin
page can add per-table notes without renaming the dataset.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "Database"
DATASET = os.getenv("DATASET", "Synthea")
DATA_ROOT = DATASETS / Path(DATASET)

DB_PATH = DATA_ROOT / "health.db"
KNOWLEDGE = DATA_ROOT / "knowledge"
TABLES = KNOWLEDGE / "tables"
THREADS_DB = DATA_ROOT / "threads.db"

_DEFAULT_LAYOUT = {
    "definitions": ["knowledge/definitions.md"],
    "tables": "knowledge/tables/{table}.md",
    "profile": None,
    "eval": "eval_set.yaml",
}


def _layout() -> dict:
    path = DATA_ROOT / "layout.json"
    if not path.is_file():
        return dict(_DEFAULT_LAYOUT)
    data = json.loads(path.read_text(encoding="utf-8"))
    definitions = data.get("definitions", _DEFAULT_LAYOUT["definitions"])
    if isinstance(definitions, str):
        definitions = [definitions]
    tables = data.get("tables", _DEFAULT_LAYOUT["tables"])
    if not isinstance(tables, str):
        raise ValueError(f"{path}: 'tables' must be a path string")
    return {
        "definitions": list(definitions),
        "tables": tables,
        "profile": data.get("profile"),
        "eval": data.get("eval", "eval_set.yaml"),
    }


LAYOUT = _layout()


def definition_paths() -> list[Path]:
    """Files concatenated into the system prompt, in listed order."""
    return [DATA_ROOT / rel for rel in LAYOUT["definitions"]]


def definitions_text() -> str:
    parts = []
    for path in definition_paths():
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def table_notes_path(table: str) -> Path:
    """Notes for one table.

    A file at knowledge/tables/<table>.md always wins, so a reviewer can
    add per-table notes on top of a shared glossary. Otherwise the layout
    `tables` pattern is used.
    """
    override = TABLES / f"{table}.md"
    if override.is_file():
        return override
    return DATA_ROOT / LAYOUT["tables"].format(table=table)


# First file in the prompt list. Prefer definition_paths() / table_notes_path().
DEFINITIONS = DATA_ROOT / Path(LAYOUT["definitions"][0])


def eval_set_path() -> Path | None:
    """Dataset eval YAML, if the file exists.

    Synthea keeps cases in `eval_cases.py` instead, so a missing file is
    normal. CMS Sample 1 ships `eval_set.yaml`.
    """
    rel = LAYOUT.get("eval") or "eval_set.yaml"
    path = DATA_ROOT / Path(rel)
    return path if path.is_file() else None
