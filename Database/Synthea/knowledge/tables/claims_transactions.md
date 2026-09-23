Line items against a claim. The biggest table and the slowest to query.

2,242,655 rows across 33 columns, and no index on any column. Every filter and
every join is a full table scan. This is the slowest thing in the database and
the most likely cause of a query hitting the 30-second timeout. Aggregate in
SQL and narrow by `CLAIMID` wherever possible.

`CLAIMID` joins to `claims.Id`, `PATIENTID` to `patients.Id`, `APPOINTMENTID`
to `encounters.Id`.

`PATIENTINSURANCEID` is not a payer link. It reads like one and it is not:
2,136,679 of its values match no row in `payers`. It is a per-patient policy
id. Joining it to `payers.Id` returns almost nothing and raises no error.

`FROMDATE` and `TODATE` are full timestamps. `TRANSFEROUTID` is declared REAL
and is not usable as a join key.
