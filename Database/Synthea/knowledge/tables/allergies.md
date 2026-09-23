Recorded allergies. Its STOP column holds no data.

2,285 rows. `START` is a plain date.

`STOP` is declared REAL and is NULL in all 2,285 rows. Any filter or
comparison against it returns nothing. Treat every allergy here as having no
end date.

`REACTION1` and `REACTION2` are also REAL and largely empty. The usable
description fields are `DESCRIPTION`, `DESCRIPTION1`, `DESCRIPTION2` and the
matching `SEVERITY1` and `SEVERITY2`.
