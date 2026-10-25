# Data Code Challenge

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
The challenge calls for solving the problem by transforming the data in two distinct ways: using pandas (Part 1) and using SQL (Part 2). You may start with whichever approach
is easiest for you.  After you've implemented the solution with one approach, you should then attempt to reimplement the solution using the other
approach as well. In either case, you should execute the query within the python interpreter using sqlalchemy.

For Part 1:
The code must be written in Python 3.9, and the solution:
- must be implemented using a `pandas` DataFrame to perform the calculations.
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


Next, create a new DataFrame illustrated in Table-2 below by performing one or more self-joins on the previously created DataFrame, applying any filtering as needed. The self-join(s) must be implemented using the `pandas` library, and, in particular, using either the `merge` or `join` functions.

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
Re-implement the logic used to produce Table-2 & Table-3 from Part 1 above. However, this time you may not use the the `pandas` `merge` or `join` functions.  Instead, you must use SQL to perform any join logic or reshaping of the data.

### Part 3

There is an additional, more comprehensive formulary dataset contained in the `formulary` database table.  This table has the same structure as the `test_formulary` table, except it contains a few extra columns (which may be ignored) and many more formularies, each of which contains many more drugs.
The target formulary for this part of the exercise is now `formulary_id = '00022170'`.  For each of the exercises below, print out the amount of time it takes for the code to execute.
* (A) Reuse your previously implemented logic to produce the same calculations for the average tier differences as described in parts (A) and (B) from Part 1 on the `formulary` table.
* (B) Reuse your previously implemented logic to produce the same calculations for the average tier differences as described in parts (A) and (B) from Part 2 on the `formulary` table.

## Running the solution

The solution targets Python 3.15 and is managed with [uv](https://docs.astral.sh/uv/):
```bash
# Install Python 3.15 and the locked dependencies into .venv
uv sync

# Part 1: compare formularies in `test_formulary`
uv run python src/solution.py

# Part 3: compare against a target formulary in `formulary`
uv run python src/solution.py 00022170
```
