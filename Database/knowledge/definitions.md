# Agreed definitions

Use these rather than inventing your own, so two answers to the same question
agree. If a question needs a definition that is not here, say which one you
used and that it was not an agreed one.

**These are placeholders pending Telligen's own grade tables.**

## Cohorts

**Living patient** — `patients.DEATHDATE` is NULL or an empty string. 2,000 of
2,311. See `knowledge/tables/patients.md` for why the empty-string check is
kept even though this build has none.

**Active condition** — `conditions.STOP` is NULL or empty.

**Type 2 diabetes** — `conditions.DESCRIPTION = 'Diabetes mellitus type 2
(disorder)'`. 189 patients. Complications are separate conditions and do not
imply the base diagnosis: kidney disorder 228, microalbuminuria 199,
proteinuria 147, neuropathy 60, retinopathy 62 across three differently spelled
descriptions. Counting any diabetes-related condition gives a larger cohort, so
say which one you used.

**Prediabetes is not diabetes.** `Prediabetes (finding)`, 830 patients. Report
it separately and never fold it into a diabetes cohort.

**Heart failure** — `Chronic congestive heart failure (disorder)` (62) or
`Heart failure (disorder)` (5). Use both: 67 distinct patients.

## Measures

**HbA1c** — `observations.DESCRIPTION = 'Hemoglobin A1c/Hemoglobin.total in
Blood'`, `TYPE = 'numeric'`, units `%`. 19,168 readings.

| Band | HbA1c |
|---|---|
| Normal | below 5.7% |
| Prediabetic range | 5.7% to 6.4% |
| Diabetic range | 6.5% and above |
| Controlled, diagnosed patient | below 7.0% |

A patient has many readings. State whether a figure is the latest reading or a
mean across readings.

**30-day readmission** — an `encounters` row with `ENCOUNTERCLASS = 'inpatient'`
starting within 30 days of a prior inpatient encounter's `STOP`. Count distinct
readmission encounters: 328. Counting discharge-to-readmission pairs instead
gives 340. There are 2,409 inpatient encounters in total, so always report the
denominator. Telligen's grade tables should settle which count is wanted.

**Age** — there is no age column. Compute it and say which date you computed it
at.

```sql
CAST((julianday('now') - julianday(p.BIRTHDATE)) / 365.25 AS INTEGER)
CAST((julianday(substr(e.START, 1, 10)) - julianday(p.BIRTHDATE)) / 365.25 AS INTEGER)
```

Unless a question says otherwise, report age bands separately: `under 18`,
`18-44`, `45-64`, `65-74`, `75+`.
