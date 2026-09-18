Insurance companies. Ten rows, mostly pre-aggregated totals.

10 rows. `ADDRESS`, `CITY`, `STATE_HEADQUARTERED`, `ZIP` and `PHONE` are
declared REAL and are NULL in every row. They hold no data.

The useful columns are the totals: `AMOUNT_COVERED`, `AMOUNT_UNCOVERED`,
`REVENUE`, the `COVERED` and `UNCOVERED` counts, `UNIQUE_CUSTOMERS` and
`MEMBER_MONTHS`. Those are already summed across the database. Re-deriving
them from `encounters` will not always agree.
