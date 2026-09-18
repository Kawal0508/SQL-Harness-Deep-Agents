Billing claims. Uses different column names from every clinical table.

258,594 rows, `Id` unique. The patient column is `PATIENTID`, not `PATIENT`.

There is no `ENCOUNTER` column. `APPOINTMENTID` is the only route from a claim
back to the visit it bills for.

`PRIMARYPATIENTINSURANCEID` and `SECONDARYPATIENTINSURANCEID` join to
`payers.Id`. `PROVIDERID` and `SUPERVISINGPROVIDERID` join to `providers.Id`.

`DIAGNOSIS1` through `DIAGNOSIS8` hold SNOMED codes, not row ids.
`DEPARTMENTID`, `PATIENTDEPARTMENTID` and `HEALTHCARECLAIMTYPEID1` and `2`
point at no table in this database.

`SERVICEDATE`, `CURRENTILLNESSDATE` and the three `LASTBILLEDDATE` columns are
all full timestamps.

Only `Id` is indexed, so every join on `PATIENTID` scans all 258,594 rows.
