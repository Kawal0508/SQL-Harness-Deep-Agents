Lab results and vitals. The largest clinical table and the easiest to get wrong.

1,819,103 rows. Three traps, all of them silent.

`VALUE` is TEXT. 703,818 rows (38.7%) hold text, not numbers. Filter
`TYPE = 'numeric'` before `CAST(VALUE AS REAL)` or the cast returns 0.0 for
every text row and drags any average down.

`CODE` is TEXT here and INTEGER everywhere else. These are LOINC codes
(`10230-1`); `conditions`, `procedures`, `medications` and `encounters` use
INTEGER SNOMED and RxNorm codes. Joining or unioning codes across those tables
without a cast returns nothing and raises no error.

62,157 rows have a NULL `ENCOUNTER` (3.4%). An inner join to `encounters`
drops all of them. Use a LEFT JOIN when the count matters.

`DATE` is a full timestamp. HbA1c readings are the rows whose `DESCRIPTION` is
`Hemoglobin A1c/Hemoglobin.total in Blood` with `TYPE = 'numeric'` and units
`%`: 18,889 of them.

No index on `VALUE`, `UNITS` or `TYPE`.
