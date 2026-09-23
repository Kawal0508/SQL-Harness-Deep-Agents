"""Synthea join map and self-check.

Loaded when Database/Synthea/layout.json sets `"profile": "tools_synthea"`.
Each edge is column -> (table, primary key). SQLite declares no foreign keys;
these were verified by counting orphans.
"""

from __future__ import annotations

_CLINICAL = {"PATIENT": ("patients", "Id"), "ENCOUNTER": ("encounters", "Id")}

EDGES: dict[str, dict[str, tuple[str, str] | list[tuple[str, str]]]] = {
    "allergies": _CLINICAL,
    "careplans": _CLINICAL,
    "conditions": _CLINICAL,
    "devices": _CLINICAL,
    "imaging_studies": _CLINICAL,
    "immunizations": _CLINICAL,
    "observations": _CLINICAL,
    "procedures": _CLINICAL,
    "supplies": _CLINICAL,
    "medications": _CLINICAL | {"PAYER": ("payers", "Id")},
    "encounters": {
        "PATIENT": ("patients", "Id"),
        "ORGANIZATION": ("organizations", "Id"),
        "PROVIDER": ("providers", "Id"),
        "PAYER": ("payers", "Id"),
    },
    "providers": {"ORGANIZATION": ("organizations", "Id")},
    "payer_transitions": {
        "PATIENT": ("patients", "Id"),
        "PAYER": ("payers", "Id"),
        "SECONDARY_PAYER": ("payers", "Id"),
    },
    "claims": {
        "PATIENTID": ("patients", "Id"),
        "APPOINTMENTID": ("encounters", "Id"),
        "PROVIDERID": ("providers", "Id"),
        "SUPERVISINGPROVIDERID": ("providers", "Id"),
        "PRIMARYPATIENTINSURANCEID": ("payers", "Id"),
        "SECONDARYPATIENTINSURANCEID": ("payers", "Id"),
    },
    "claims_transactions": {
        "CLAIMID": ("claims", "Id"),
        "PATIENTID": ("patients", "Id"),
        "APPOINTMENTID": ("encounters", "Id"),
        "PROVIDERID": ("providers", "Id"),
        "SUPERVISINGPROVIDERID": ("providers", "Id"),
    },
}


def self_check(describe_schema, run_sql) -> None:
    listing = describe_schema()
    assert "patients" in listing and "observations" in listing, listing
    assert "Did you mean: patients?" in describe_schema("atient")
    assert "BIRTHDATE" in describe_schema("patients")

    counted = run_sql("SELECT COUNT(*) AS n FROM patients")
    assert '"n": 2311' in counted, counted

    capped = run_sql("SELECT Id FROM patients", limit=5)
    assert "row_count: 5" in capped and "TRUNCATED" in capped, capped

    for statement in (
        "DROP TABLE patients",
        "DELETE FROM patients",
        "INSERT INTO patients (Id) VALUES ('x')",
        "UPDATE patients SET FIRST = 'x'",
        "PRAGMA table_info(patients)",
        "SELECT 1; DROP TABLE patients",
    ):
        refusal = run_sql(statement)
        assert "rows:" not in refusal, f"{statement!r} was not refused: {refusal}"
