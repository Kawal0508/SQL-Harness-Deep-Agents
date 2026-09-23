DICOM imaging. One row per instance, many rows per study.

208,830 rows but only 11,615 distinct `Id`. `COUNT(*)` overstates the number of
studies by about 18 times. Count studies with `COUNT(DISTINCT Id)`.

`DATE` is a full timestamp. `MODALITY_CODE` and `SOP_CODE` are TEXT;
`BODYSITE_CODE` and `PROCEDURE_CODE` are INTEGER.
