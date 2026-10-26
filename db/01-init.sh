#!/bin/bash
set -euo pipefail
DATA_DIR=${DATA_DIR:-/data}

# The app user owns the database (and so its public schema) rather than being a
# superuser; \copy reads the files client-side, so it needs no extra privileges.
export PGPASSWORD=$POSTGRES_PASSWORD
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE ROLE $APP_DB_USER WITH LOGIN PASSWORD '$APP_DB_PASS';
  CREATE DATABASE $APP_DB_NAME OWNER $APP_DB_USER;
EOSQL

# (formulary_id, rxcui) is the key the comparison assumes, so the database
# enforces it. Both are codes rather than prose, so they use the byte-order "C"
# collation: sorting on them is several times faster than with en_US, and the
# order matches polars. Keys are added after loading, which is faster than
# checking them row by row, and VACUUM ANALYZE gives the planner statistics.
# The load is one transaction, so if any step fails no tables exist and the
# healthcheck in docker-compose.yml keeps failing instead of passing on an
# empty or half-loaded database.
export PGPASSWORD=$APP_DB_PASS
psql -v ON_ERROR_STOP=1 --username "$APP_DB_USER" --dbname "$APP_DB_NAME" <<-EOSQL
  BEGIN;
  CREATE TABLE test_formulary(
    FORMULARY_ID TEXT COLLATE "C" NOT NULL,
    TIER_LEVEL_VALUE INT NOT NULL,
    RXCUI TEXT COLLATE "C" NOT NULL
  );
  CREATE TABLE formulary(
    FORMULARY_ID TEXT COLLATE "C" NOT NULL,
    FORMULARY_VERSION TEXT NOT NULL,
    CONTRACT_YEAR TEXT NOT NULL,
    RXCUI TEXT COLLATE "C" NOT NULL,
    NDC TEXT,
    TIER_LEVEL_VALUE INT NOT NULL,
    QUANTITY_LIMIT_YN TEXT,
    QUANTITY_LIMIT_AMOUNT TEXT,
    QUANTITY_LIMIT_DAYS TEXT,
    PRIOR_AUTHORIZATION_YN TEXT,
    STEP_THERAPY_YN TEXT
  );

  \copy test_formulary FROM '$DATA_DIR/test_formulary.txt' DELIMITER '|' CSV HEADER
  -- An extract can hold several editions of a formulary (a contract year and
  -- version); comparing them together would mix plans, and the primary key
  -- would reject the load. Keep each formulary's latest edition.
  CREATE TEMPORARY TABLE formulary_load (LIKE formulary) ON COMMIT DROP;
  \copy formulary_load FROM PROGRAM 'tar -xzOf $DATA_DIR/full_formulary.tar.gz full_formulary.txt' DELIMITER '|' CSV HEADER
  INSERT INTO formulary
  SELECT FORMULARY_ID, FORMULARY_VERSION, CONTRACT_YEAR, RXCUI, NDC, TIER_LEVEL_VALUE,
    QUANTITY_LIMIT_YN, QUANTITY_LIMIT_AMOUNT, QUANTITY_LIMIT_DAYS,
    PRIOR_AUTHORIZATION_YN, STEP_THERAPY_YN
  FROM (
    SELECT *, rank() OVER (
      PARTITION BY FORMULARY_ID
      ORDER BY CONTRACT_YEAR::int DESC, FORMULARY_VERSION::int DESC
    ) AS edition
    FROM formulary_load
  ) AS ranked
  WHERE edition = 1;

  ALTER TABLE test_formulary ADD PRIMARY KEY (FORMULARY_ID, RXCUI);
  ALTER TABLE formulary ADD PRIMARY KEY (FORMULARY_ID, RXCUI);
  COMMIT;

  VACUUM ANALYZE test_formulary;
  VACUUM ANALYZE formulary;
EOSQL
