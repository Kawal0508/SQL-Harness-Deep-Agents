Prescriptions. Carries a payer link the other clinical tables do not.

121,823 rows. `START` and `STOP` are full timestamps. `STOP` is NULL on 6,092
rows, which is how an active prescription reads.

`PAYER` joins to `payers.Id`. Besides `encounters` this is the only clinical
table that reaches a payer directly, and the column is not indexed.

No primary key, so count people with `COUNT(DISTINCT PATIENT)`.
