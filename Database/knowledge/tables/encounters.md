One row per visit. The second hub: most clinical rows carry its `Id`.

137,678 rows, `Id` unique. Indexed on `Id`, `PATIENT`, `CODE`, `DESCRIPTION`.

`START` and `STOP` are full timestamps (`2016-09-22T21:16:05Z`) and are never
NULL. Use `substr(START, 1, 10)` when comparing against a plain-date column
such as `patients.BIRTHDATE` or `conditions.START`.

`ENCOUNTERCLASS` values: `ambulatory`, `wellness`, `outpatient`, `urgentcare`,
`emergency`, `inpatient`, `home`, `hospice`, `snf`, `virtual`. There are 2,409
inpatient encounters; report that denominator with any readmission figure.
`ENCOUNTERCLASS` is not indexed, so filtering on it scans all 137,678 rows.

Links out to `organizations`, `providers` and `payers`. None of those three
columns is indexed, so those joins scan.
