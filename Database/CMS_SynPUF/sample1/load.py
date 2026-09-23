"""Build health.db from CMS DE-SynPUF Sample 1 CSVs.

    python Database/CMS_SynPUF/sample1/load.py
    python Database/CMS_SynPUF/sample1/load.py --force
    DATASET=CMS_SynPUF/sample1 python Database/CMS_SynPUF/sample1/load.py --force

Same typing rules as Database/Synthea/load.py: empty CSV fields become NULL,
column types are inferred from values, not from sqlite3 .import.

Table names match the Sample 1 eval set. The two carrier claim files are
concatenated into one `carrier` table.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_DIR = ROOT / "raw"
DB_PATH = ROOT / "health.db"

BATCH = 5_000

# Eval-set names. Filenames are CMS DE-SynPUF Sample 1 exports in raw/.
SOURCES: list[tuple[str, tuple[str, ...]]] = [
    ("bene_2008", ("DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv",)),
    ("bene_2009", ("DE1_0_2009_Beneficiary_Summary_File_Sample_1.csv",)),
    ("bene_2010", ("DE1_0_2010_Beneficiary_Summary_File_Sample_1.csv",)),
    ("inpatient", ("DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv",)),
    ("outpatient", ("DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv",)),
    (
        "carrier",
        (
            "DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.csv",
            "DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.csv",
        ),
    ),
    ("pde", ("DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.csv",)),
]

INDEXES: dict[str, list[str]] = {
    "bene_2008": ["DESYNPUF_ID"],
    "bene_2009": ["DESYNPUF_ID"],
    "bene_2010": ["DESYNPUF_ID"],
    "inpatient": ["DESYNPUF_ID", "CLM_ID"],
    "outpatient": ["DESYNPUF_ID", "CLM_ID"],
    "carrier": ["DESYNPUF_ID", "CLM_ID"],
    "pde": ["DESYNPUF_ID", "PDE_ID"],
}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


class Column:
    """Type inference for one column, fed one value at a time.

    The rules, in the order they resolve:
      all integers and no blanks  -> INTEGER
      integers with blanks, or any real number -> REAL
      no values at all            -> REAL
      anything else               -> TEXT
    """

    def __init__(self) -> None:
        self.text = False
        self.real = False
        self.blank = False
        self.seen = False

    def feed(self, value: str) -> None:
        if value == "":
            self.blank = True
            return
        self.seen = True
        if self.text:
            return
        try:
            int(value)
            return
        except ValueError:
            pass
        try:
            float(value)
            self.real = True
        except ValueError:
            self.text = True

    @property
    def type(self) -> str:
        if self.text:
            return "TEXT"
        if not self.seen:
            return "REAL"
        if self.real or self.blank:
            return "REAL"
        return "INTEGER"


def infer(paths: list[Path]) -> tuple[list[str], list[str]]:
    """Return the header and one SQLite type per column, across all files."""
    header: list[str] | None = None
    columns: list[Column] | None = None
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            this_header = next(reader, None)
            if this_header is None:
                raise SystemExit(f"{path.name} is empty, not even a header")
            if header is None:
                header = this_header
                columns = [Column() for _ in header]
            elif this_header != header:
                raise SystemExit(
                    f"{path.name} header does not match {paths[0].name}"
                )
            assert columns is not None
            for row in reader:
                for column, value in zip(columns, row):
                    column.feed(value)
    assert header is not None and columns is not None
    return header, [column.type for column in columns]


def convert(value: str, type_: str):
    """An empty field is NULL, never ''."""
    if value == "":
        return None
    if type_ == "INTEGER":
        return int(value)
    if type_ == "REAL":
        return float(value)
    return value


def insert_file(
    db: sqlite3.Connection, path: Path, insert: str, header: list[str], types: list[str]
) -> int:
    total = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        batch = []
        for row in reader:
            row += [""] * (len(header) - len(row))
            batch.append(tuple(convert(v, t) for v, t in zip(row, types)))
            if len(batch) >= BATCH:
                db.executemany(insert, batch)
                total += len(batch)
                batch.clear()
        if batch:
            db.executemany(insert, batch)
            total += len(batch)
    return total


def load_table(db: sqlite3.Connection, table: str, paths: list[Path]) -> int:
    header, types = infer(paths)
    columns = ", ".join(f'"{name}" {type_}' for name, type_ in zip(header, types))
    db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.execute(f'CREATE TABLE "{table}" ({columns})')
    placeholders = ", ".join("?" * len(header))
    insert = f'INSERT INTO "{table}" VALUES ({placeholders})'
    total = 0
    for path in paths:
        n = insert_file(db, path, insert, header, types)
        extra = f"  ({path.name})" if len(paths) > 1 else ""
        print(f"{table:<22} {n:>9,} rows{extra}", flush=True)
        total += n
    db.commit()
    return total


def index(db: sqlite3.Connection) -> None:
    for table, columns in INDEXES.items():
        for column in columns:
            unique = "UNIQUE " if column == "DESYNPUF_ID" and table.startswith("bene_") else ""
            db.execute(
                f'CREATE {unique}INDEX "ix_{table}_{column}" '
                f'ON "{table}" ("{column}")'
            )
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=CSV_DIR)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--force", action="store_true",
                        help="replace an existing database")
    args = parser.parse_args()

    planned = [(table, [args.csv_dir / name for name in names]) for table, names in SOURCES]
    missing = [path for _, paths in planned for path in paths if not path.is_file()]
    if missing:
        names = ", ".join(path.name for path in missing)
        raise SystemExit(f"Missing CSVs in {args.csv_dir}: {names}")
    if args.db.exists() and not args.force:
        raise SystemExit(f"{args.db} exists. Pass --force to replace it.")
    if args.db.exists():
        args.db.unlink()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.db)
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    try:
        for table, paths in planned:
            load_table(db, table, paths)
        index(db)
        db.execute("VACUUM")
    finally:
        db.close()
    print(f"\nWrote {args.db}")
    print("Switch the harness with: DATASET=CMS_SynPUF/sample1")


if __name__ == "__main__":
    main()
