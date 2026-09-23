# Glossary — CMS DE-SynPUF encodings

Source of truth for code values. Adapters should ingest this file rather than re-encoding the codebook in Python.

## Chronic condition flags (`SP_*`)

These columns appear on `bene_2008`, `bene_2009`, and `bene_2010`.

| Value | Meaning |
| --- | --- |
| `1` | Beneficiary has the condition |
| `2` | Beneficiary does not have the condition |

There is no `0` = no. Treating these as boolean 0/1 is wrong.

| Column | Condition |
| --- | --- |
| `SP_ALZHDMTA` | Alzheimer's / related disorders or senile dementia |
| `SP_CHF` | Congestive heart failure |
| `SP_CHRNKIDN` | Chronic kidney disease |
| `SP_CNCR` | Cancer |
| `SP_COPD` | Chronic obstructive pulmonary disease |
| `SP_DEPRESSN` | Depression |
| `SP_DIABETES` | Diabetes |
| `SP_ISCHMCHT` | Ischemic heart disease |
| `SP_OSTEOPRS` | Osteoporosis |
| `SP_RA_OA` | Rheumatoid arthritis / osteoarthritis |
| `SP_STRKETIA` | Stroke / transient ischemic attack |

Example: `SP_DIABETES = 1` means the beneficiary has diabetes.

`SP_CHF = 1` is the beneficiary-summary CHF flag. Claim-level CHF uses ICD-9 codes in `knowledge/codesets/icd9_chf.txt` — those are not the same filter.

## Sex

`BENE_SEX_IDENT_CD`

| Value | Meaning |
| --- | --- |
| `1` | Male |
| `2` | Female |

## Race

`BENE_RACE_CD`

| Value | Meaning |
| --- | --- |
| `1` | White |
| `2` | Black |
| `3` | Other |
| `5` | Hispanic |

## ESRD

`BENE_ESRD_IND`

| Value | Meaning |
| --- | --- |
| `Y` | End-stage renal disease |
| `0` | No ESRD |

## Coverage months

Each is an integer 0–12 for that calendar year:

- `BENE_HI_CVRAGE_TOT_MONS` — Part A (hospital insurance)
- `BENE_SMI_CVRAGE_TOT_MONS` — Part B (supplementary medical insurance)
- `BENE_HMO_CVRAGE_TOT_MONS` — HMO
- `PLAN_CVRG_MOS_NUM` — Part D plan

“Enrolled all year” usually means the relevant coverage column equals 12.

## Identifiers

| Column | Meaning |
| --- | --- |
| `DESYNPUF_ID` | Synthetic beneficiary id (join key) |
| `CLM_ID` | Claim id |
| `PDE_ID` | Prescription drug event id |
| `SEGMENT` | Claim segment number |

## Dates

All DE-SynPUF dates in this extract are `YYYYMMDD` with no separators (`20080103`). Blank `BENE_DEATH_DT` means death is not recorded in that year’s summary file.
