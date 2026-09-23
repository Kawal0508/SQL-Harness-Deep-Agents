"""CMS DE-SynPUF Sample 1 join map and self-check.

Loaded when Database/CMS_SynPUF/sample1/layout.json sets `"profile": "tools_cms"`.
Claim tables join to all three yearly beneficiary files on DESYNPUF_ID; which
year to use is a query choice, not a declared foreign key.
"""

from __future__ import annotations

_BENE = [
    ("bene_2008", "DESYNPUF_ID"),
    ("bene_2009", "DESYNPUF_ID"),
    ("bene_2010", "DESYNPUF_ID"),
]

EDGES: dict[str, dict[str, tuple[str, str] | list[tuple[str, str]]]] = {
    "inpatient": {"DESYNPUF_ID": _BENE},
    "outpatient": {"DESYNPUF_ID": _BENE},
    "carrier": {"DESYNPUF_ID": _BENE},
    "pde": {"DESYNPUF_ID": _BENE},
}


def self_check(describe_schema, run_sql) -> None:
    listing = describe_schema()
    assert "bene_2009" in listing and "inpatient" in listing, listing
    assert "DESYNPUF_ID" in describe_schema("bene_2009")

    counted = run_sql("SELECT COUNT(*) AS n FROM bene_2009")
    assert '"n": 114538' in counted, counted

    capped = run_sql("SELECT DESYNPUF_ID FROM bene_2009", limit=5)
    assert "row_count: 5" in capped and "TRUNCATED" in capped, capped
