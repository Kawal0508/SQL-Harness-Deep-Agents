Clinicians. Each belongs to one organization.

1,075 rows, `Id` unique and indexed. `ORGANIZATION` joins to
`organizations.Id` and is not indexed.

`ENCOUNTERS` and `PROCEDURES` are pre-computed counts for that provider, not
foreign keys. `SPECIALITY` is spelled with the extra I.
