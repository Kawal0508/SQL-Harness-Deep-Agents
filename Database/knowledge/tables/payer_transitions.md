Insurance coverage periods. Uses its own date column names.

83,316 rows. The date columns are `START_DATE` and `END_DATE`, not `START` and
`STOP`. Both are full timestamps.

`PAYER` and `SECONDARY_PAYER` both join to `payers.Id`. `SECONDARY_PAYER` is
populated on 6,731 rows. Only `PATIENT` is indexed.
