One row per synthetic person. Every clinical table points here.

2,281 rows, 2,281 distinct `Id`. This is the hub of the database.

`BIRTHDATE` and `DEATHDATE` are plain dates (`2016-09-22`), not timestamps.
There is no age column. Compute age and say which date you computed it at.

A living patient is one with no `DEATHDATE`: 2,000 of 2,281. In this build the
column is NULL in all 2,000 and holds a date in the other 281, so there are no
empty strings and `IS NULL` alone is correct. The longer form
`DEATHDATE IS NULL OR DEATHDATE = ''` returns the same 2,000 and survives a
rebuild that reintroduces empty strings.

`FIPS`, `LAT`, `LON`, `HEALTHCARE_EXPENSES` and `HEALTHCARE_COVERAGE` are REAL.
`ZIP` and `INCOME` are INTEGER. Everything else is TEXT.
