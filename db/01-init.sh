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
# order matches pandas. Keys are added after loading, which is faster than
# checking them row by row, and VACUUM ANALYZE gives the planner statistics.
export PGPASSWORD=$APP_DB_PASS
psql -v ON_ERROR_STOP=1 --username "$APP_DB_USER" --dbname "$APP_DB_NAME" <<-EOSQL
  CREATE TABLE test_formulary(
    FORMULARY_ID TEXT COLLATE "C" NOT NULL,
    TIER_LEVEL_VALUE INT NOT NULL,
    RXCUI TEXT COLLATE "C" NOT NULL
  );
  CREATE TABLE formulary(
    FORMULARY_ID TEXT COLLATE "C" NOT NULL,
    FORMULARY_VERSION TEXT,
    CONTRACT_YEAR TEXT,
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
  \copy formulary FROM PROGRAM 'tar -xzOf $DATA_DIR/full_formulary.tar.gz full_formulary.txt' DELIMITER '|' CSV HEADER

  ALTER TABLE test_formulary ADD PRIMARY KEY (FORMULARY_ID, RXCUI);
  ALTER TABLE formulary ADD PRIMARY KEY (FORMULARY_ID, RXCUI);
  VACUUM ANALYZE test_formulary;
  VACUUM ANALYZE formulary;
EOSQL
