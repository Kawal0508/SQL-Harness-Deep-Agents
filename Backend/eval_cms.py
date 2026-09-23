"""Score CMS `eval_set.yaml` against the live database.

Not the Synthea agent eval (`eval.py` / `eval_cases.py`). This runs the
DuckDB `gold_sql` in Database/CMS_SynPUF/sample1/eval_set.yaml against
`health.db`, fills `USER_INPUT`, and aggregates by tier and trap.

    DATASET=CMS_SynPUF/sample1 python eval_cms.py
    DATASET=CMS_SynPUF/sample1 python eval_cms.py --list
    DATASET=CMS_SynPUF/sample1 python eval_cms.py --only L1-001
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

from paths import DB_PATH, DATASET, eval_set_path

USER_INPUT = "USER_INPUT"
TABLE_PREVIEW = 8
UNFILLED = {None, "", USER_INPUT}


def load_eval_set(path: Path) -> tuple[dict, list[dict]]:
    """Parse the CMS YAML: a `meta:` mapping followed by a case list.

    That shape is not a single YAML document. Split on the first `- id:`
    rather than requiring the file to be rewritten.
    """
    import yaml

    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None

    if isinstance(data, list):
        return {}, [c for c in data if isinstance(c, dict) and "id" in c]
    if isinstance(data, dict):
        cases = data.get("cases") or data.get("questions")
        if isinstance(cases, list):
            meta = data.get("meta")
            if not isinstance(meta, dict):
                meta = {k: v for k, v in data.items() if k not in ("cases", "questions")}
            return meta, [c for c in cases if isinstance(c, dict) and "id" in c]

    idx = next(
        (i for i, line in enumerate(text.splitlines()) if line.startswith("- id:")),
        None,
    )
    if idx is None:
        raise ValueError(f"{path}: no cases found")
    lines = text.splitlines(keepends=True)
    meta_doc = yaml.safe_load("".join(lines[:idx])) or {}
    if isinstance(meta_doc, dict) and "meta" in meta_doc:
        meta_doc = meta_doc["meta"]
    cases = yaml.safe_load("".join(lines[idx:]))
    if not isinstance(cases, list):
        raise ValueError(f"{path}: case block is not a list")
    return meta_doc if isinstance(meta_doc, dict) else {}, [
        c for c in cases if isinstance(c, dict) and "id" in c
    ]


def _connect(db_path: Path):
    import duckdb

    if not db_path.is_file():
        raise FileNotFoundError(f"No database at {db_path}.")
    con = duckdb.connect()
    target = str(db_path.resolve()).replace("'", "''")
    attach = f"ATTACH '{target}' AS cms (TYPE SQLITE, READ_ONLY)"
    try:
        con.execute(attach)
    except Exception:
        con.execute("INSTALL sqlite")
        con.execute("LOAD sqlite")
        con.execute(attach)
    # load.py stores YYYYMMDD dates as INTEGER/REAL. Gold SQL treats them as
    # CHAR(8), so expose one view per table with *_DT columns as text.
    con.execute("CREATE SCHEMA gold")
    tables = [
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_catalog = 'cms' AND table_type = 'BASE TABLE'"
        ).fetchall()
    ]
    for table in tables:
        cols = con.execute(f"DESCRIBE cms.{table}").fetchall()
        replacements = []
        for col, typ, *_rest in cols:
            if not str(col).upper().endswith("_DT"):
                continue
            if "CHAR" in str(typ).upper() or "TEXT" in str(typ).upper():
                continue
            replacements.append(
                "CASE WHEN {c} IS NULL THEN NULL ELSE "
                "lpad(CAST(CAST({c} AS BIGINT) AS VARCHAR), 8, '0') END AS {c}".format(
                    c=col
                )
            )
        if replacements:
            sql = (
                f"CREATE VIEW gold.{table} AS SELECT * REPLACE ("
                + ", ".join(replacements)
                + f") FROM cms.{table}"
            )
        else:
            sql = f"CREATE VIEW gold.{table} AS SELECT * FROM cms.{table}"
        con.execute(sql)
    con.execute("USE gold")
    return con


def _cell(value):
    if value is None or isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def execute(con, sql) -> tuple[list[str] | None, list[tuple] | None, str | None]:
    if sql is None:
        return None, None, None
    text = str(sql).strip()
    if not text or text.lower() in {"null", "none"}:
        return None, None, None
    try:
        rel = con.execute(text)
        cols = [d[0] for d in rel.description] if rel.description else []
        rows = [tuple(_cell(v) for v in row) for row in rel.fetchall()]
        return cols, rows, None
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def _scalar(rows) -> object | None:
    if not rows:
        return None
    if len(rows[0]) != 1:
        return None
    return rows[0][0]


def answers_match(got, want, tolerance) -> bool | None:
    if want in UNFILLED:
        return None
    if got is None:
        return False
    try:
        gf, wf = float(got), float(want)
    except (TypeError, ValueError):
        return got == want
    tol = 0.0 if tolerance is None else float(tolerance)
    if tol > 0:
        return abs(gf - wf) <= tol or math.isclose(gf, wf, rel_tol=0.0, abs_tol=tol)
    return math.isclose(gf, wf, rel_tol=1e-9, abs_tol=1e-9)


def rows_equal(a, b, tolerance) -> bool:
    if a is None or b is None or len(a) != len(b):
        return False
    tol = 0.0 if tolerance is None else float(tolerance)
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb):
            if x == y:
                continue
            try:
                xf, yf = float(x), float(y)
            except (TypeError, ValueError):
                return False
            if not (
                abs(xf - yf) <= max(tol, 1e-9)
                or math.isclose(xf, yf, rel_tol=1e-9, abs_tol=max(tol, 1e-9))
            ):
                return False
    return True


def fmt_value(value, cols=None, rows=None, answer_type: str = "scalar") -> str:
    if answer_type == "abstention":
        return "ABSTAIN"
    if answer_type == "table" and rows is not None:
        preview = rows[:TABLE_PREVIEW]
        body = json.dumps(preview, default=str, ensure_ascii=False)
        extra = "" if len(rows) <= TABLE_PREVIEW else f" … +{len(rows) - TABLE_PREVIEW}"
        return f"table n={len(rows)} {body}{extra}"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e12:
            return f"{value:,.0f}"
        return f"{value:.6g}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _recorded_scalar(case: dict):
    want = case.get("gold_answer")
    if want in UNFILLED:
        return USER_INPUT
    return want


def score_case(con, case: dict) -> dict:
    answer_type = case.get("answer_type") or "scalar"
    want = case.get("gold_answer")
    traps = list(case.get("traps") or [])
    result = {
        "id": case["id"],
        "tier": case.get("tier") or "",
        "question": case.get("question") or "",
        "answer_type": answer_type,
        "traps": traps,
        "want": want,
        "got": None,
        "cols": None,
        "rows": None,
        "gold_error": None,
        "gold_ok": None,
        "unfilled": want in UNFILLED,
        "wrong_error": None,
        "trap_dead": None,
    }

    if answer_type == "abstention" or case.get("gold_sql") is None:
        result["got"] = "ABSTAIN"
        result["gold_ok"] = str(want).upper() in {"ABSTAIN", "USER_INPUT"} or want in UNFILLED
        if want in UNFILLED:
            result["unfilled"] = True
            result["gold_ok"] = None
        return result

    cols, rows, err = execute(con, case.get("gold_sql"))
    result["cols"], result["rows"], result["gold_error"] = cols, rows, err
    if err:
        result["gold_ok"] = False
        return result

    if answer_type == "scalar":
        got = _scalar(rows)
        result["got"] = got
        result["gold_ok"] = answers_match(got, want, case.get("tolerance"))
    else:
        result["got"] = rows
        result["gold_ok"] = None if want in UNFILLED else None

    wrong = case.get("wrong_sql")
    if wrong and not err:
        wcols, wrows, werr = execute(con, wrong)
        result["wrong_error"] = werr
        if werr:
            result["trap_dead"] = False
        else:
            result["trap_dead"] = rows_equal(rows, wrows, case.get("tolerance"))
    return result


def inventory(meta: dict, cases: list[dict]) -> str:
    lines = [
        f"# {meta.get('dataset') or DATASET} eval set\n",
        f"{len(cases)} cases"
        + (
            f" (meta.total_cases={meta['total_cases']})"
            if meta.get("total_cases") is not None
            else ""
        )
        + f". Dialect `{meta.get('dialect') or 'duckdb'}` "
        f"against `{DB_PATH}`.\n",
    ]
    by_tier = Counter(c.get("tier") or "?" for c in cases)
    by_type = Counter(c.get("answer_type") or "scalar" for c in cases)
    lines.append("| Tier | n |")
    lines.append("|---|---|")
    for name, n in by_tier.items():
        lines.append(f"| {name} | {n} |")
    lines.append("")
    lines.append("| Answer type | n |")
    lines.append("|---|---|")
    for name, n in by_type.items():
        lines.append(f"| {name} | {n} |")
    lines.append("")
    trap_n = Counter()
    for case in cases:
        for trap in case.get("traps") or []:
            trap_n[trap] += 1
    if trap_n:
        lines.append("| Trap | n |")
        lines.append("|---|---|")
        for name, n in trap_n.most_common():
            lines.append(f"| {name} | {n} |")
        lines.append("")
    unfilled = sum(1 for c in cases if c.get("gold_answer") in UNFILLED)
    lines.append(
        f"{unfilled} cases still have `gold_answer: USER_INPUT`. "
        f"{sum(1 for c in cases if c.get('wrong_sql'))} have `wrong_sql`.\n"
    )
    return "\n".join(lines)


def print_list(scored: list[dict]) -> None:
    for row in scored:
        if row["gold_error"]:
            shown = "ERROR"
        elif row["unfilled"] or row["gold_ok"] is None:
            shown = fmt_value(
                row["got"], row["cols"], row["rows"], row["answer_type"]
            )
        else:
            shown = fmt_value(row["got"], row["cols"], row["rows"], row["answer_type"])
            if row["gold_ok"] is False:
                shown = f"{shown} (yaml {row['want']})"
        mark = ""
        if row["gold_error"]:
            mark = "ERR "
        elif row["gold_ok"] is False:
            mark = "MIS "
        elif row["unfilled"] and row["answer_type"] != "abstention":
            mark = "FILL"
        elif row["trap_dead"]:
            mark = "DEAD"
        print(f"{mark:<4} {row['id']:<10} {shown:>22}  {row['question']}")


def print_report(meta: dict, cases: list[dict], scored: list[dict]) -> int:
    print(inventory(meta, cases))
    gold_ok = sum(1 for r in scored if r["gold_ok"] is True)
    gold_bad = sum(1 for r in scored if r["gold_ok"] is False)
    gold_err = [r for r in scored if r["gold_error"]]
    filled = [r for r in scored if r["unfilled"] and r["got"] is not None and not r["gold_error"]]
    dead = [r for r in scored if r["trap_dead"]]
    checked = [r for r in scored if r["trap_dead"] is not None]

    print(
        f"**Gold SQL:** {gold_ok} match the YAML, {gold_bad} disagree, "
        f"{len(gold_err)} failed to run, {len(filled)} were USER_INPUT "
        f"and are shown below.\n"
    )
    print(
        f"**Traps:** {len(dead)} of {len(checked)} `wrong_sql` queries "
        f"returned the same result as gold (dead trap).\n"
    )

    by_tier: dict[str, list[dict]] = {}
    for row in scored:
        by_tier.setdefault(row["tier"] or "?", []).append(row)
    print("| | Tier | Ran | YAML match | USER_INPUT filled | SQL error | Dead trap |")
    print("|---|---|---|---|---|---|---|")
    for tier, rows in by_tier.items():
        ran = sum(1 for r in rows if r["gold_error"] is None and r["answer_type"] != "abstention")
        match = sum(1 for r in rows if r["gold_ok"] is True)
        fill = sum(1 for r in rows if r["unfilled"] and not r["gold_error"])
        err = sum(1 for r in rows if r["gold_error"])
        dead_n = sum(1 for r in rows if r["trap_dead"])
        print(f"| | {tier} | {ran} | {match} | {fill} | {err} | {dead_n} |")

    trap_rows: dict[str, list[dict]] = {}
    for row in scored:
        for trap in row["traps"]:
            trap_rows.setdefault(trap, []).append(row)
    if trap_rows:
        print("\n| Trap | n | Dead |")
        print("|---|---|---|")
        for trap, rows in sorted(trap_rows.items(), key=lambda kv: -len(kv[1])):
            print(f"| {trap} | {len(rows)} | {sum(1 for r in rows if r['trap_dead'])} |")

    if gold_err:
        print("\n## Gold SQL errors\n")
        for row in gold_err:
            print(f"- `{row['id']}`: {row['gold_error']}")

    mismatches = [r for r in scored if r["gold_ok"] is False and not r["gold_error"]]
    if mismatches:
        print("\n## YAML disagrees with live DB\n")
        for row in mismatches:
            print(
                f"- `{row['id']}`: yaml {row['want']!r}, "
                f"live {fmt_value(row['got'], row['cols'], row['rows'], row['answer_type'])}"
            )

    if filled:
        print("\n## USER_INPUT filled from live DB\n")
        for row in filled:
            print(
                f"- `{row['id']}`: "
                f"{fmt_value(row['got'], row['cols'], row['rows'], row['answer_type'])}"
            )

    if dead:
        print("\n## Dead traps (`wrong_sql` == gold)\n")
        for row in dead:
            print(f"- `{row['id']}` traps={row['traps']}")

    failed = bool(gold_err or mismatches)
    return 1 if failed else 0


def main(path: Path, list_only: bool = False, only: str | None = None) -> int:
    meta, cases = load_eval_set(path)
    if only:
        cases = [c for c in cases if c["id"] == only]
        if not cases:
            print(f"No case named {only!r}.", file=sys.stderr)
            return 2
    print(f"eval set {path}  ({DATASET})", file=sys.stderr)
    con = _connect(DB_PATH)
    try:
        scored = []
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case['id']}", file=sys.stderr, flush=True)
            scored.append(score_case(con, case))
    finally:
        con.close()
    if list_only:
        print_list(scored)
        return 0 if not any(r["gold_error"] for r in scored) else 1
    return print_report(meta, cases, scored)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="one line per case")
    parser.add_argument("--only", metavar="ID", help="run a single case")
    args = parser.parse_args()
    path = eval_set_path()
    if path is None:
        sys.exit(
            f"No eval_set.yaml under dataset {DATASET!r}. "
            "Set DATASET=CMS_SynPUF/sample1."
        )
    sys.exit(main(path, list_only=args.list, only=args.only))
