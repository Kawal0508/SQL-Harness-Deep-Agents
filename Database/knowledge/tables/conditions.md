SNOMED findings recorded against a patient. Not a list of diseases.

83,592 rows. The most common entry is `Medication review due (situation)`,
recorded for all 2,281 patients across 17,401 rows. `Stress (finding)`,
`Full-time employment (finding)` and `Social isolation (finding)` are all in
the top fifteen. Counting rows here and calling the result a disease count is
wrong. Filter on specific `DESCRIPTION` values.

`START` and `STOP` are plain dates, not timestamps. `STOP` is NULL on 20,469
rows and is never an empty string in this build. An active condition is one
with no `STOP`.

A patient can hold the same condition more than once and there is no primary
key, so count people with `COUNT(DISTINCT PATIENT)`.

Exact description strings matter and are not spelled consistently. Type 2
diabetes is `Diabetes mellitus type 2 (disorder)`, 183 patients. The
retinopathy complications switch to roman numerals and drop the suffix:
`Nonproliferative diabetic retinopathy due to type II diabetes mellitus` (59
patients), `Proliferative diabetic retinopathy due to type II diabetes
mellitus` (6), `Macular edema and retinopathy due to type 2 diabetes mellitus
(disorder)` (6). Guessing a string from the shape of another one returns zero
rows.
