DICOM imaging. One row per instance, many rows per study.

185,188 rows but only 11,210 distinct `Id`. `COUNT(*)` overstates the number of
studies by about 16.5 times. Count studies with `COUNT(DISTINCT Id)`.

`DATE` is a full timestamp. `MODALITY_CODE` and `SOP_CODE` are TEXT;
`BODYSITE_CODE` and `PROCEDURE_CODE` are INTEGER.
