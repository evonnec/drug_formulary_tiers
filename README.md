# Drug Formulary Tiers

Compares Medicare drug formularies by how far their drug tiers sit from a target
formulary's, two ways: with polars, and with SQL on Postgres. The challenge it answers
comes first; the implementation is under [Solution](#solution).

## Background

In Medicare, health insurance plans use a standardized formulary structure to administer prescription drug coverage. The formulary is a list of drugs that are covered by the plan. On the formulary, a drug is represented by an identifier called the _RXCUI_ (a unique, unambiguous identifier that is assigned to an individual drug entity). Typically, the drugs in a formulary are organized into a 6-tier structure - consequently, each drug on the formulary can be assigned an integer tier value between 1 and 6, inclusive. A drug placed on a higher tier typically implies that the plan beneficiary will have to pay a higher out-of-pocket cost for that drug.

We would like to perform a comparison analysis that calculates the average drug tier difference between formularies. To do this, we will use a Postgres database running in a Docker container, via the following command:
```bash
# Initialize the Postgres container and load the requisite datasets
docker compose up

# You may then connect to the database (via your client of choice) with the following credentials:
#   Username: appuser
#   Password: appuser
#   Database: formulary
#   Host/Port: localhost:5432
# For example:
psql -hlocalhost -p5432 -Uappuser -W formulary
```

The `formulary` database contains a table named `test_formulary` with the following columns:

* `formulary_id`
* `tier_level_value`
* `rxcui`

There are 5 distinct formularies represented in the `test_formulary`, each of which is uniquely identified by a `formulary_id`. Each formulary is associated with a set of drugs, and each drug is assigned to one of 6 tiers, indicated by the `rxcui` and `tier_level_value` columns, respectively. Note that the tuple `(formulary_id, rxcui)` forms a unique key in this table.

The goal is to compare every formulary against a target formulary by calculating the average tier difference between the associated drugs. The target formulary for this exercise is identified by `formulary_id = '00019356'`. The target formulary should not be compared against itself.

To simplify the analysis, for each pair of formularies compared, if one formulary contains a drug that the other does not, you must assign a tier value of `7` to the "uncovered" drug.

### Requirements

**Notes:**
The challenge calls for solving the problem by transforming the data in two distinct ways: using polars (Part 1) and using SQL (Part 2). You may start with whichever approach
is easiest for you.  After you've implemented the solution with one approach, you should then attempt to reimplement the solution using the other
approach as well. In either case, you should execute the query within the python interpreter using sqlalchemy.

> **Note:** executing every query through SQLAlchemy was the requirement when this
> challenge was written, years ago. The solution still connects and builds its queries
> with SQLAlchemy, but on Postgres it reads large results over `COPY` on that
> connection, because executing them through SQLAlchemy is slower: 2.6s against 1.8s
> to fetch Table-2's 1.66M rows, with about 100 MB more memory.

For Part 1:
The code must be written in Python 3.15 or later, and the solution:
- must be implemented using a `polars` DataFrame to perform the calculations.
- the DataFrame should contain a single calculated average tier difference value for each `formulary_id` compared against the target formulary.
- should be implemented using functions with well-defined interfaces.


## Problem

### Part 1

In order to perform this analysis, the data must first be loaded from the database into a DataFrame, allowing the column-wise tier differences between drugs for every pair of formularies to be easily calculated.

Extract the data from the `test_formulary` database table and load the data into a DataFrame containing the 3 columns as illustrated in Table-1 below.

__Table-1__

formulary\_id | tier\_level\_value | rxcui
------------- | ------------------ | -----
00019356 | 1 | 1001
00019356 | 2 | 1002
00019356 | 3 | 1003
00019100 | 2 | 1001
00019100 | 1 | 1002
00019100 | 3 | 1004
00019200 | 3 | 1001
00019200 | 1 | 1002
00019200 | 2 | 1005
00019300 | 3 | 1001
00019300 | 3 | 1002
00019300 | 3 | 1003
00019400 | 1 | 1004
00019400 | 2 | 1005
00019400 | 3 | 1006


Next, create a new DataFrame illustrated in Table-2 below by performing one or more self-joins on the previously created DataFrame, applying any filtering as needed. The self-join(s) must be implemented using the `polars` library, and, in particular, using its `join` function.

__Table-2__

formulary\_target\_id | tier\_level\_value\_target | rxcui | formulary\_id | tier\_level\_value
--------------------- | -------------------------- | ----- | ------------- | ------------------
00019356 | 1 | 1001 | 00019100 | 2
00019356 | 2 | 1002 | 00019100 | 1
00019356 | 3 | 1003 | 00019100 | 7
00019356 | 7 | 1004 | 00019100 | 3
00019356 | 1 | 1001 | 00019200 | 3
00019356 | 2 | 1002 | 00019200 | 1
00019356 | 3 | 1003 | 00019200 | 7
00019356 | 7 | 1005 | 00019200 | 2
00019356 | 1 | 1001 | 00019300 | 3
00019356 | 2 | 1002 | 00019300 | 3
00019356 | 3 | 1003 | 00019300 | 3
00019356 | 1 | 1001 | 00019400 | 7
00019356 | 2 | 1002 | 00019400 | 7
00019356 | 3 | 1003 | 00019400 | 7
00019356 | 7 | 1004 | 00019400 | 1
00019356 | 7 | 1005 | 00019400 | 2
00019356 | 7 | 1006 | 00019400 | 3


For each unique value of `formulary_id` in the table (excluding the target `formulary_id`), we want to compare the `tier_level_value`s for all `rxcui`s against the `tier_level_value`s for the `rxcui`s on the target formulary.  Specifically, the difference should be calculated as `tier_level_value_target` - `tier_level_value`.

For each comparison between two formularies:
* (A) Calculate the average difference between tiers for all `rxcui`s.
* (B) Calculate the average difference between tiers for all `rxcui`s except those where the tiers are the same.

In both cases, the results should map the `formulary_id` to the average tier difference calculated (e.g. in a series or DataFrame).

The results produced for both parts (A) and (B) should look something like this:

__Table-3__

formulary\_id | tier\_difference
------------- | ----------------
00019100 | some_value_1
00019200 | some_value_2
00019300 | some_value_3
00019400 | some_value_4


Once you are confident you have correctly implemented the logic to produce the DataFrames illustrated in Table-2 and Table-3 above, proceed to part 2.

### Part 2
Re-implement the logic used to produce Table-2 & Table-3 from Part 1 above. However, this time you may not use the `polars` `join` function.  Instead, you must use SQL to perform any join logic or reshaping of the data.

### Part 3

There is an additional, more comprehensive formulary dataset contained in the `formulary` database table.  This table has the same structure as the `test_formulary` table, except it contains a few extra columns (which may be ignored) and many more formularies, each of which contains many more drugs.
The target formulary for this part of the exercise is now `formulary_id = '00022170'`.  For each of the exercises below, print out the amount of time it takes for the code to execute.
* (A) Reuse your previously implemented logic to produce the same calculations for the average tier differences as described in parts (A) and (B) from Part 1 on the `formulary` table.
* (B) Reuse your previously implemented logic to produce the same calculations for the average tier differences as described in parts (A) and (B) from Part 2 on the `formulary` table.

## Solution

The solution targets Python 3.15, uses [polars](https://pola.rs) for its DataFrames, and
is managed with [uv](https://docs.astral.sh/uv/).

```bash
docker compose up --detach --wait   # Postgres with both tables loaded
uv sync                             # Python 3.15 and the locked dependencies

uv run formulary-tiers 1            # Part 1: polars on test_formulary
uv run formulary-tiers 2            # Part 2: SQL on test_formulary
uv run formulary-tiers 3            # Part 3: both on formulary, with timings
uv run formulary-tiers 3 --target 00022000   # any other target formulary
```

`db/01-init.sh` only runs when the container is first created, so after changing it run
`docker compose down --volumes` before `docker compose up` again.

### Layout

| Module | Responsibility |
| --- | --- |
| `src/drug_formulary_tiers/polars_solution.py` | Part 1: Table-2 and Table-3 as pure functions of a DataFrame |
| `src/drug_formulary_tiers/sql_solution.py` | Part 2: `SqlComparison`, the same tables computed in SQL and run through SQLAlchemy |
| `src/drug_formulary_tiers/db.py` | Connection settings (`DATABASE_URL` overrides them) and the Table-1 extract |
| `src/drug_formulary_tiers/schema.py` | Table schemas, the uncovered tier (7), input validation |
| `src/drug_formulary_tiers/cli.py` | `formulary-tiers {1,2,3}`: runs a part and prints each table with timings |

### Approach

Each formulary is compared with the target on the union of their drugs. Both solutions
build Table-2 the same way:

1. Pair every formulary other than the target with every target drug (a cross join), so
   the drugs a formulary lacks get a row.
2. Full outer join that with the formularies' own drugs on `(formulary_id, rxcui)`,
   which adds the drugs the target lacks.
3. Give whichever side is missing tier 7.

Table-3 averages `tier_level_value_target - tier_level_value` per formulary. A
formulary whose drugs all match the target keeps its row in (B) with a null average, so
(A) and (B) always list the same formularies.

- **polars** averages Table-2 directly. For (B), equal tiers become null
  (`when/then`), so the average skips them.
- **SQL** computes (A) and (B) in one pass without building Table-2. Over the union of a
  formulary's drugs and the target's, the differences always sum to
  `Σ(target tier - 7) + Σ(7 - formulary tier)`, whatever drugs the two share. Only the
  counts need the drugs they share, so each row is joined to the target's few thousand
  drugs instead of building the 1.7M-row full join.

Both are linear in the size of the data. The original solution self-joined the whole
table on `rxcui` alone, building a 514M-row intermediate that took about 7 minutes.

On Postgres, both solutions read their rows over `COPY ... TO STDOUT` as CSV, which
polars parses directly. That uses about a fifth of the memory of building a Python
object per value, and it is faster than executing the query through SQLAlchemy (see
the note under Requirements). Other databases, such as SQLite in the tests, fetch rows
the usual way.

### Results

For the README example, target `00019356`:

| formulary_id | (A) all drugs | (B) drugs on different tiers |
| --- | --- | --- |
| 00019100 | 0.0 | 0.0 |
| 00019200 | 0.0 | 0.0 |
| 00019300 | -1.0 | -1.5 |
| 00019400 | 0.0 | 0.0 |

Part 3, target `00022170`, compares 457 formularies. Three of them (`00022153`,
`00022258`, `00022360`) match the target exactly, so their (B) average is null. Timings
are medians of three runs on an Apple silicon laptop against a local Postgres:

| Step | polars | SQL |
| --- | --- | --- |
| Check the table | included in Table-2 | 0.06s |
| Load Table-1 (1,583,463 rows) | 1.0s | — |
| Table-2 (1,659,527 rows) | 0.3s | not fetched: Part 3 needs only Table-3 |
| Table-3 (A) and (B) | 0.04s | 0.2s, one query |

The SQL solution computes Table-3 without Table-2, so Part 3 skips fetching Table-2's
rows; `formulary-tiers 2` prints SQL Table-2 for the README example. Peak memory for the
whole `formulary-tiers 3` run is about 0.8 GB.

### Edge cases and data quality

Both solutions run the same checks before comparing:

- **Target not in the table:** `TargetNotFoundError`; the CLI exits with status 1.
- **Duplicate `(formulary_id, rxcui)` keys, or null ids or tiers:** `FormularyDataError`.
  The database also rejects them with a primary key and `NOT NULL`, but the SQL
  solution checks anyway, since other databases may not.
- **Wrong types:** the polars solution requires text ids and integer tiers, so `1.9`
  isn't silently truncated and `"00019356"` doesn't become `19356`.
- **Tiers outside 1-6:** the full dataset has 102 rows on tier 7 (formularies
  `00022158` and `00022161`). A covered drug on tier 7 cannot be told apart from an
  uncovered one, so these rows are kept and both solutions log a warning.
- **Formulary sharing no drugs with the target** (`00019400`): compared on both drug
  sets, with every drug uncovered on one side.
- **Target as the only formulary:** empty Table-2 and Table-3 with the usual columns.
- **SQL safety:** table names are checked against an allowlist before going into SQL,
  and the target is always a bind parameter.
- **Row order:** both solutions sort Table-2 by `(formulary_id, rxcui)` in byte order
  with polars, whatever the database's collation. Sorting 1.7M rows took Postgres longer
  than joining them.

### Database

`db/01-init.sh` and `docker-compose.yml`:

- One transaction loads both tables and adds a primary key on `(formulary_id, rxcui)`
  and `NOT NULL` on the columns the comparison uses. It is followed by `VACUUM ANALYZE`.
- An extract can hold several editions of a formulary (a contract year and version).
  Only each formulary's latest edition is loaded, by contract year and then version, so
  plans aren't mixed and the primary key holds. The data here has one edition per
  formulary, so all 1,583,463 rows load.
- `formulary_id` and `rxcui` use the byte-order `"C"` collation, since they are codes
  rather than prose. Comparing them, and building and scanning the primary key, is
  cheaper than under `en_US`.
- When the table has a unique index on its key, as the primary key here is, the SQL
  check trusts it instead of counting duplicates. That is most of the check's cost.
- `appuser` owns the `formulary` database instead of being a superuser.
- The image is pinned to `postgres:18`, and the port is only published on localhost.
- The healthcheck queries the loaded data over TCP. `docker compose up --wait` returns
  only once the load has committed, and a container restarted after a failed load stays
  unhealthy instead of serving an empty database.

### Tests

```bash
uv run pytest                  # test
uv run ruff check              # lint
uv run mypy                    # type check
uv run ruff format --check     # format
```

- The README's Table-1, Table-2 and Table-3 are fixtures that both solutions must
  reproduce exactly.
- Property-based tests (Hypothesis) compare both solutions on random formularies with a
  brute-force reading of the rules in `tests/oracle.py`, which shares no code with the
  package. The generated data includes tier 7 and mixed-case and non-ASCII ids.
- The SQL tests run on SQLite, and also on Postgres when `TEST_DATABASE_URL` is set.
  With it set, `tests/test_postgres.py` also checks the schema and data
  `db/01-init.sh` creates, and checks both solutions on the full `formulary` table
  against exact reference values and the brute-force reference:
  ```bash
  TEST_DATABASE_URL=postgresql+psycopg://appuser:appuser@localhost:5432/formulary uv run pytest
  ```

CI runs all four checks on every pull request and push to `main`. The test job starts
the database with `docker compose`, and the suite refuses to run in CI without
`TEST_DATABASE_URL`, so the Postgres tests can't be skipped there unnoticed.
