Prescriptions. Carries a payer link the other clinical tables do not.

122,682 rows. `START` and `STOP` are full timestamps. `STOP` is NULL on 5,990
rows, which is how an active prescription reads.

`PAYER` joins to `payers.Id`. Besides `encounters` this is the only clinical
table that reaches a payer directly, and the column is not indexed.

No primary key, so count people with `COUNT(DISTINCT PATIENT)`.
