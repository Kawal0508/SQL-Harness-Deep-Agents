Lab results and vitals. The largest clinical table and the easiest to get wrong.

1,830,903 rows. Three traps, all of them silent.

`VALUE` is TEXT. 706,415 rows (38.6%) hold text, not numbers. Filter
`TYPE = 'numeric'` before `CAST(VALUE AS REAL)` or the cast returns 0.0 for
every text row and drags any average down.

`CODE` is TEXT here and INTEGER everywhere else. These are LOINC codes
(`10230-1`); `conditions`, `procedures`, `medications` and `encounters` use
INTEGER SNOMED and RxNorm codes. Joining or unioning codes across those tables
without a cast returns nothing and raises no error.

62,532 rows have a NULL `ENCOUNTER` (3.4%). An inner join to `encounters`
drops all of them. Use a LEFT JOIN when the count matters.

`DATE` is a full timestamp. HbA1c readings are the rows whose `DESCRIPTION` is
`Hemoglobin A1c/Hemoglobin.total in Blood` with `TYPE = 'numeric'` and units
`%`: 19,168 of them.

283 distinct `DESCRIPTION` values. `SELECT DISTINCT DESCRIPTION FROM
observations` lists what is actually measured, which is cheaper and surer than
guessing at `LIKE` patterns.

Blood type is not one of them. Synthea generates no ABO group and no Rh factor,
here or in `patients`, so no query can answer a question about blood group. Say
so rather than searching for it. `DESCRIPTION LIKE '%ABO%'` looks like a hit and
is not: it matches "about" in the PRAPARE survey questions.

No index on `VALUE`, `UNITS` or `TYPE`.
