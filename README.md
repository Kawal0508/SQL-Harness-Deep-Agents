# Agentic harness for synthetic health data

Ask a question in plain English. The agent writes SQL, shows it to you, and
waits. You approve, edit, or reject it. Approved queries run against a
read-only SQLite database, and the answer comes back with the rows and the
reasoning behind them.

Built on [Deep Agents](https://github.com/langchain-ai/deepagents) (LangChain,
MIT). Data is Synthea-generated: 2,311 synthetic Iowa residents, 18 tables, no
real patients and no PHI.

## Folders

```
Database/     health.db, the Synthea generator, and what the data means
  knowledge/
    tables/   one .md per table: what it holds and what goes wrong
    definitions.md   cohort rules, HbA1c bands, readmission definition
Backend/      Python. Two services and the agent they share
Frontend/     index.html, admin.html. No build step, no framework
```

`knowledge/` lives under `Database/` because it documents the tables, not the
code. It stays useful if the Python is replaced. `Backend/instructions.md` is
the opposite: prompt text, so it sits with the code.

### Backend

| File | Role |
|---|---|
| `tools.py` | The two tools: `run_sql` and `describe_schema`. Read-only enforcement lives here. No framework imports, so it works under any harness. |
| `agent.py` | Deep Agents wiring. Strips the eight built-in filesystem and shell tools. Terminal loop. |
| `api.py` | Agent service, port 8000. Streams a turn to the browser and exposes the approval gate over HTTP. |
| `admin.py` | Admin service, port 8001. The only write connection in the codebase. |
| `instructions.md` | System prompt. |
| `eval.py`, `eval_cases.py` | Graded accuracy and measured cost. |

## Setup

Python 3.11 or newer. The repository was developed on 3.13.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env          # then add your key
```

`ANTHROPIC_API_KEY` is required for anything that calls the model. Deep Agents
reaches Anthropic through `langchain-anthropic`, which authenticates with an
API key only — a Claude Code or subscription login cannot be reused.

### Regenerating the database

`Database/health.db` is gitignored. Regenerate it in two steps, and pin both.

```bash
cd Database
java -jar synthea-with-dependencies.jar \
  -p 2000 -s 20260911 -cs 20260911 -r 20260911 -e 20260911 \
  --exporter.baseDirectory ./synthea_output \
  --exporter.csv.export true \
  Iowa
```

`-e` is the flag that matters. `-r` sets the reference date but not the end of
the simulation, so without `-e` Synthea runs through today and the population
grows by a few patients for every day that passes. Pinned this way the run is
deterministic: the same 2,311 patients, 2,000 of them living, at any thread
count. Row order in the CSVs varies between runs; the contents do not.

Then load `synthea_output/csv/*.csv` into `health.db`. Do not use
`sqlite3 .import`. It creates untyped columns, stores every empty CSV field as
an empty string rather than NULL, and builds no indexes — which silently
inverts most of what `knowledge/` documents. `IS NULL` returns nothing,
`allergies.STOP` stops being REAL, and the join columns `encounters` is
documented as indexed on are gone. The loader must:

- write NULL for an empty field, not `''`
- type each column from its values: all-integer and no blanks gives INTEGER, an
  integer column with blanks or any real number gives REAL, an entirely empty
  column gives REAL, anything else TEXT
- index `encounters(Id, PATIENT, CODE, DESCRIPTION)`, `claims(Id)`,
  `organizations(Id)`, `providers(Id)` and `payer_transitions(PATIENT)`, and
  leave `claims_transactions` unindexed

`python Backend/tools.py` checks the result. It fails if the row count or the
read-only guarantees do not hold.

## Run

Both services start from `Backend/`:

```bash
cd Backend

uvicorn api:app   --reload --port 8000    # agent, read-only
uvicorn admin:app --reload --port 8001    # admin, write
```

Open <http://localhost:8000>.

Two processes on purpose. The agent service opens the database read-only; the
admin service is the only thing that can write to it. Splitting them means a
bug on the agent path cannot reach a write connection, because that process
does not have one.

There is also a terminal client, no web server needed:

```bash
cd Backend
python agent.py              # queries run unattended
python agent.py --approve    # y/n before every query
```

## Checks that need no API key

Run these first. All three work offline and cost nothing.

```bash
cd Backend
python tools.py              # read-only self-check, every refusal case
python agent.py --check-tools  # asserts the model is offered exactly two tools
python eval.py --list        # computes ground truth from the live database
```

`--check-tools` exists because two failure modes are silent. Deep Agents ships
eight built-in tools and `tools=` only adds to them, so if the harness profile
fails to resolve, the model quietly keeps filesystem and shell access. The
assertion catches that.

With a key set, `python eval.py` runs the graded set and prints accuracy and
measured cost. `eval_cases.py` documents what the number does not cover.

## How the approval gate works

The obvious design is two endpoints: one returns the SQL, the other takes it
back to execute. That shape lets the client send back a different query than
the one it was shown, so the server would have to re-validate the string on
every call.

This uses LangGraph interrupts instead. The SQL never leaves the server. The
browser receives a description and returns a decision:

```
{"type": "approve"}
{"type": "reject", "message": "..."}
{"type": "edit", "edited_action": {"name": "run_sql", "args": {...}}}
```

Editing the query box and pressing Approve sends `edit`, so the edited SQL is
what runs. Rejecting produces a tool error the model has to account for, rather
than a fake success.

One question can gate more than once. The page loops: stream, decide, stream
again.

## How the agent learns the schema

Two steps, on demand, no vector store.

1. `describe_schema()` returns every table, its row count, and one line on what
   it holds. This is the index.
2. `describe_schema('conditions')` returns that table's columns, indexes,
   verified joins, and the full text of `Database/knowledge/tables/conditions.md`.

The model reads the index, picks the tables it needs, and pulls only those. The
notes carry what the column names do not show. Real examples from this
database:

- `allergies.STOP` is declared REAL and is NULL in all 2,285 rows. Any filter
  against it returns nothing.
- `observations.CODE` is TEXT while every other `CODE` column is INTEGER.
  Joining across them silently returns nothing.
- `imaging_studies.Id` is not unique. 208,830 rows hold 11,615 studies, so
  `COUNT(*)` overstates by about 18 times.
- `claims_transactions.PATIENTINSURANCEID` reads like a foreign key to
  `payers`. It is not — 2,136,679 of its values match no payer.
- `claims_transactions` has 2.2M rows and no index on any column.

No foreign keys are declared anywhere in this database. The join map in
`tools.py` was verified by counting orphan rows, not read off the column names.

## Adding a table

Use the admin service at <http://localhost:8001>. Upload a CSV, then write the
table's notes. The first line of those notes becomes the summary the agent sees
in its index, so it should say what the table holds in one line.

The agent service picks up the change without a restart — its row-count cache
is keyed on the database file's mtime, so a write from the other process
invalidates it.

Dropping a table requires typing its name, and deletes its notes file too.
Left behind, those notes would silently attach to the next table created under
the same name.

## Read-only enforcement

Three layers, on the agent path only:

1. The connection is opened with SQLite's `mode=ro` URI flag.
2. An authorizer callback rejects every operation that is not a read, inside
   the engine, before a statement executes. This catches what a parser would
   miss.
3. Deploy the agent service as an OS user with no write permission on
   `health.db`. Not code — a deployment step, and the only layer that survives
   a bug in the other two.

`sqlite3.Cursor.execute` refuses more than one statement per call, so stacked
queries are rejected without extra work.

`tools.py` has no write-capable connect function. Not behind a flag, not behind
an environment variable — absent.

## Known limits

- **Sessions do not survive a restart.** The checkpointer is `InMemorySaver`,
  so a pending approval resumes into nothing after the server restarts.
  Upgrading is `pip install langgraph-checkpoint-sqlite` and two lines.
- **No authentication on either service.** Single-user local tool. The admin
  service needs it first.
- **Prompt-injection testing is not done.** The authorizer limits the damage;
  it does not prevent the attempt.
- **No Python execution, no charts, no HTML reports.** The proposal asks for
  these. They are a separate milestone because generated Python is a much
  larger threat model than generated SQL, and read-only database access does
  not contain it.
- **The definitions are placeholders** pending Telligen's own grade tables.
  Ground truth in `eval_cases.py` is only as agreed as `definitions.md` is.
