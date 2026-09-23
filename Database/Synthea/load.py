"""Build health.db from Synthea's CSV export.

    python Database/Synthea/load.py                 # synthea_output/csv -> health.db
    python Database/Synthea/load.py --force         # overwrite an existing health.db
    python Database/Synthea/load.py --db /tmp/x.db  # build somewhere else

`sqlite3 .import` is not a substitute. It gives every column TEXT affinity,
stores an empty CSV field as '' rather than NULL, and creates no indexes,
which quietly inverts most of what `knowledge/` documents: `IS NULL` matches
nothing, `allergies.STOP` stops being REAL, and the joins `encounters` is
documented as indexed on are gone.

Each file is read twice. The first pass decides one type per column from the
values themselves; the second inserts. Nothing is held in memory but the
current batch, because claims_transactions.csv is a gigabyte on its own.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_DIR = ROOT / "synthea_output" / "csv"
DB_PATH = ROOT / "health.db"

BATCH = 5_000

# Only the columns the knowledge files promise are indexed. Id columns are
# unique; the rest are not. claims_transactions is deliberately absent: it is
# the largest table and nothing joins to it.
INDEXES: dict[str, list[str]] = {
    "encounters": ["Id", "PATIENT", "CODE", "DESCRIPTION"],
    "claims": ["Id"],
    "organizations": ["Id"],
    "providers": ["Id"],
    "payer_transitions": ["PATIENT"],
}

# Synthea writes a header row even for a table it produced no rows for, so an
# empty file still yields a typed, empty table.
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


def infer(path: Path) -> tuple[list[str], list[str]]:
    """Return the header and one SQLite type per column."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            raise SystemExit(f"{path.name} is empty, not even a header")
        columns = [Column() for _ in header]
        for row in reader:
            for column, value in zip(columns, row):
                column.feed(value)
    return header, [column.type for column in columns]


def convert(value: str, type_: str):
    """An empty field is NULL, never ''. That distinction is the whole point."""
    if value == "":
        return None
    if type_ == "INTEGER":
        return int(value)
    if type_ == "REAL":
        return float(value)
    return value


def load_table(db: sqlite3.Connection, path: Path) -> int:
    table = path.stem
    header, types = infer(path)
    columns = ", ".join(f'"{name}" {type_}' for name, type_ in zip(header, types))
    db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.execute(f'CREATE TABLE "{table}" ({columns})')

    placeholders = ", ".join("?" * len(header))
    insert = f'INSERT INTO "{table}" VALUES ({placeholders})'
    total = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        batch = []
        for row in reader:
            # A short row means a trailing empty field the writer dropped.
            row += [""] * (len(header) - len(row))
            batch.append(tuple(convert(v, t) for v, t in zip(row, types)))
            if len(batch) >= BATCH:
                db.executemany(insert, batch)
                total += len(batch)
                batch.clear()
        if batch:
            db.executemany(insert, batch)
            total += len(batch)
    db.commit()
    return total


def index(db: sqlite3.Connection) -> None:
    for table, columns in INDEXES.items():
        for column in columns:
            unique = "UNIQUE " if column == "Id" else ""
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

    files = sorted(args.csv_dir.glob("*.csv"))
    if not files:
        raise SystemExit(
            f"No CSVs in {args.csv_dir}. Run Synthea first; see the README."
        )
    if args.db.exists() and not args.force:
        raise SystemExit(f"{args.db} exists. Pass --force to replace it.")
    if args.db.exists():
        args.db.unlink()

    db = sqlite3.connect(args.db)
    # Durability buys nothing here: a failed load is rebuilt, not recovered.
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    try:
        for path in files:
            rows = load_table(db, path)
            print(f"{path.stem:<22} {rows:>9,} rows", flush=True)
        index(db)
        db.execute("VACUUM")
    finally:
        db.close()
    print(f"\nWrote {args.db}. Verify with: python Backend/tools.py")


if __name__ == "__main__":
    main()
