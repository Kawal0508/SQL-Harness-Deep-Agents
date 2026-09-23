"""Filesystem layout for the active dataset.

Every `health.db`, `knowledge/`, and `threads.db` path is derived here.
Datasets live under `Database/<name>/`. Switch with `DATASET` (default
`Synthea`). A second dataset is another directory of the same shape.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "Database"
DATASET = os.getenv("DATASET", "Synthea")
DATA_ROOT = DATASETS / DATASET

DB_PATH = DATA_ROOT / "health.db"
KNOWLEDGE = DATA_ROOT / "knowledge"
TABLES = KNOWLEDGE / "tables"
DEFINITIONS = KNOWLEDGE / "definitions.md"
THREADS_DB = DATA_ROOT / "threads.db"
