# Reporting and safety rules

Apply these when executing gold SQL, adapter SQL, and when publishing `results/`.

## Small-cell suppression

CMS public-use reporting practice for this project:

- Do **not** release a cell whose count of beneficiaries or claims is **strictly less than 11**.
- Replace such cells with a suppressed marker (e.g. `*`) rather than the raw count.
- Rates and percentages whose numerator or denominator would be `< 11` are also suppressed.
- Complementary suppression: if a suppressed cell can be recovered from a total minus the remaining cells, suppress an additional cell.

This is a reporting rule, not a database constraint. DuckDB will still return small counts; the eval runner / report layer is responsible for applying suppression on published output.

## Read-only queries

Adapters may only issue `SELECT` / `WITH … SELECT`. No `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `COPY`, or `ATTACH`. Enforced later by `db/guard.py`.

## Row cap

Do not return unbounded result sets to the model or the report. Default cap: 10,000 rows (`db/guard.py`).

## Synthetic data reminder

DE-SynPUF is synthetic. It is still treated as sensitive for suppression practice so the harness matches real CMS workflows. Do not attempt to re-identify, and do not mix these files with real beneficiary data in the same database.
