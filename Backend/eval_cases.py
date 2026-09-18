"""Evaluation questions for the health-database agent.

Every case is a natural-language question whose correct answer is a single
number, plus the SQL that produces that number. Ground truth is computed from
the live database at run time rather than hard-coded, so rebuilding `health.db`
does not silently invalidate the set.

Cases are chosen so that a *naive* answer differs from the correct one. A
question both a careful and a careless agent get right measures nothing. The
`targets` field names the documented rule the case exercises and `naive_error`
names what going wrong looks like, so a failure is diagnosable without rerunning.

This file has no imports and knows nothing about the harness. It outlived one
harness change already; keep it that way.

KNOWN LIMITATIONS
-----------------
1. These are not Telligen's questions. Survey question 05 asks the client for
   five real analyst questions; until those arrive, this set is derived from the
   project's own instructions and proves the harness applies its documented
   rules - not that it answers the questions Telligen actually has.
2. Every answer is a single number. Questions whose answer is a ranking, a
   table, a trend or a judgement are not covered, and the agent's caveats and
   prose are not graded at all. A case can pass with an unhelpful explanation.
3. `instructions.md` calls its own definitions placeholders pending Telligen's
   grade tables. Ground truth here is only as agreed as that file is.
4. Grading is exact-match on a number. An answer that is right but reported
   against a different denominator, or right by luck from wrong SQL, scores the
   same as a well-reasoned one. The `sql` field is captured for every case so a
   pass can be audited, but it is not checked automatically.
5. The set is small and every case is single-hop. It says nothing about
   multi-step reasoning, long sessions, or prompt-injection resistance.
6. Synthea data is not clinically realistic - the A1c case's own ground truth
   sits below physiological range. The harness is measured on fidelity to the
   database, not on clinical plausibility.
7. Ground truth is written by the same project that wrote the rules being
   tested, so a case can encode a mistake as the right answer. The
   readmissions-30day case did exactly that under the previous harness: the
   agent was marked wrong for answering 266 when the truth SQL said 317, and the
   agent was right. Treat a single failure as a question about the case before
   it is a question about the agent.

OPEN QUESTION FOR TELLIGEN
--------------------------
The 30-day readmission definition does not say whether an encounter readmitted
within 30 days of two earlier discharges counts once or twice. Distinct
encounters gives 266, discharge-readmission pairs gives 275. This set uses 266,
matching "an encounters row" in the definition. Telligen's grade tables should
settle it.
"""

from __future__ import annotations

CASES: list[dict] = [
    {
        "id": "living-patients",
        "question": "How many living patients are in the database?",
        "targets": "living-patient rule: DEATHDATE empty string, not just NULL",
        "naive_error": "answering 2281 (every patient) or filtering on IS NULL alone",
        "truth_sql": """
            SELECT COUNT(*) AS n FROM patients
            WHERE DEATHDATE IS NULL OR DEATHDATE = ''
        """,
    },
    {
        "id": "t2dm-cohort",
        "question": "How many patients have type 2 diabetes?",
        "targets": "exact DESCRIPTION 'Diabetes mellitus type 2 (disorder)'",
        "naive_error": "DESCRIPTION LIKE '%diabet%', which sweeps in complications and prediabetes",
        "truth_sql": """
            SELECT COUNT(DISTINCT PATIENT) AS n FROM conditions
            WHERE DESCRIPTION = 'Diabetes mellitus type 2 (disorder)'
        """,
    },
    {
        "id": "prediabetes-separate",
        "question": "How many patients have prediabetes?",
        "targets": "prediabetes is reported separately, never folded into diabetes",
        "naive_error": "returning the diabetes cohort, or the two summed",
        "truth_sql": """
            SELECT COUNT(DISTINCT PATIENT) AS n FROM conditions
            WHERE DESCRIPTION = 'Prediabetes (finding)'
        """,
    },
    {
        "id": "heart-failure-cohort",
        "question": "How many patients have heart failure?",
        "targets": "the cohort is two DESCRIPTION values, not one",
        "naive_error": "answering 50 by using only 'Chronic congestive heart failure (disorder)'",
        "truth_sql": """
            SELECT COUNT(DISTINCT PATIENT) AS n FROM conditions
            WHERE DESCRIPTION IN (
                'Chronic congestive heart failure (disorder)',
                'Heart failure (disorder)'
            )
        """,
    },
    {
        "id": "a1c-numeric-readings",
        "question": "How many HbA1c readings are in the database?",
        "targets": "rule 2: observations.VALUE is text, filter TYPE = 'numeric'",
        "naive_error": "counting rows without the TYPE filter",
        "truth_sql": """
            SELECT COUNT(*) AS n FROM observations
            WHERE DESCRIPTION = 'Hemoglobin A1c/Hemoglobin.total in Blood'
              AND TYPE = 'numeric'
        """,
    },
    {
        "id": "a1c-controlled",
        "question": (
            "Among patients with type 2 diabetes, how many have a latest HbA1c "
            "reading in the controlled range?"
        ),
        "targets": "the 'controlled' band (<7.0%) plus the latest-vs-mean rule",
        "naive_error": "averaging all readings per patient instead of taking the latest",
        "truth_sql": """
            WITH dm AS (
                SELECT DISTINCT PATIENT FROM conditions
                WHERE DESCRIPTION = 'Diabetes mellitus type 2 (disorder)'
            ),
            ranked AS (
                SELECT o.PATIENT, CAST(o.VALUE AS REAL) AS v,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.PATIENT ORDER BY o.DATE DESC
                       ) AS rn
                FROM observations o
                JOIN dm ON dm.PATIENT = o.PATIENT
                WHERE o.DESCRIPTION = 'Hemoglobin A1c/Hemoglobin.total in Blood'
                  AND o.TYPE = 'numeric'
            )
            SELECT COUNT(*) AS n FROM ranked WHERE rn = 1 AND v < 7.0
        """,
    },
    {
        "id": "encounters-2016",
        "question": "How many patients had an encounter in 2016?",
        "targets": "rule 1: encounters.START is a full timestamp",
        "naive_error": "COUNT(*) of encounters instead of distinct patients, or START = '2016'",
        "truth_sql": """
            SELECT COUNT(DISTINCT PATIENT) AS n FROM encounters
            WHERE substr(START, 1, 4) = '2016'
        """,
    },
    {
        "id": "active-conditions",
        "question": "How many patients have at least one active condition?",
        "targets": "active condition: STOP is NULL or empty",
        "naive_error": "counting condition rows, or treating empty string as a stop date",
        "truth_sql": """
            SELECT COUNT(DISTINCT PATIENT) AS n FROM conditions
            WHERE STOP IS NULL OR STOP = ''
        """,
    },
    {
        "id": "medicated-patients",
        "question": "How many patients have been prescribed at least one medication?",
        "targets": "medications has no primary key, use COUNT(DISTINCT PATIENT)",
        "naive_error": "answering 122682, the row count",
        "truth_sql": "SELECT COUNT(DISTINCT PATIENT) AS n FROM medications",
    },
    {
        "id": "inpatient-denominator",
        "question": "How many inpatient encounters are there?",
        "targets": "ENCOUNTERCLASS values; the readmission denominator",
        "naive_error": "matching on DESCRIPTION or counting all encounters",
        "truth_sql": """
            SELECT COUNT(*) AS n FROM encounters
            WHERE ENCOUNTERCLASS = 'inpatient'
        """,
    },
    {
        "id": "readmissions-30day",
        "question": "How many 30-day inpatient readmissions are there?",
        "targets": (
            "30-day readmission: 'an encounters row', so count distinct "
            "readmission encounters, measured off the prior STOP"
        ),
        "naive_error": (
            "COUNT(*) over the join, which counts pairs - an encounter readmitted "
            "within 30 days of two earlier discharges is then counted twice (275)"
        ),
        # Both START and STOP are timestamps here, so they compare directly.
        # substr() truncation belongs in joins across the date-only tables and
        # shifts boundary cases if applied here.
        "truth_sql": """
            SELECT COUNT(DISTINCT b.Id) AS n
            FROM encounters a
            JOIN encounters b
              ON b.PATIENT = a.PATIENT
             AND b.ENCOUNTERCLASS = 'inpatient'
             AND julianday(b.START) > julianday(a.STOP)
             AND julianday(b.START) - julianday(a.STOP) <= 30
            WHERE a.ENCOUNTERCLASS = 'inpatient'
        """,
    },
    {
        "id": "living-over-65",
        "question": "How many living patients are 65 or older today?",
        "targets": "age computation (no age column) combined with the living rule",
        "naive_error": "ignoring DEATHDATE, or subtracting birth years instead of using julianday",
        "truth_sql": """
            SELECT COUNT(*) AS n FROM patients
            WHERE (DEATHDATE IS NULL OR DEATHDATE = '')
              AND CAST((julianday('now') - julianday(BIRTHDATE)) / 365.25
                       AS INTEGER) >= 65
        """,
    },
]
