#!/bin/bash
set -e
export PGPASSWORD=$POSTGRES_PASSWORD;

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE USER $APP_DB_USER WITH PASSWORD '$APP_DB_PASS';
  CREATE DATABASE $APP_DB_NAME;
  GRANT ALL PRIVILEGES ON DATABASE $APP_DB_NAME TO $APP_DB_USER;
  \connect $APP_DB_NAME $APP_DB_USER
  BEGIN;
  CREATE TABLE IF NOT EXISTS formulary(
    FORMULARY_ID TEXT,
    FORMULARY_VERSION TEXT,
    CONTRACT_YEAR TEXT,
    RXCUI TEXT,
    NDC TEXT,
    TIER_LEVEL_VALUE INT,
    QUANTITY_LIMIT_YN TEXT,
    QUANTITY_LIMIT_AMOUNT TEXT,
    QUANTITY_LIMIT_DAYS TEXT,
    PRIOR_AUTHORIZATION_YN TEXT,
    STEP_THERAPY_YN  TEXT
  );
  CREATE TABLE IF NOT EXISTS test_formulary(
    FORMULARY_ID TEXT,
    TIER_LEVEL_VALUE INT,
    RXCUI TEXT
  );

  COMMIT;

EOSQL

psql --username "$APP_DB_USER" --dbname "$APP_DB_NAME" \
  -c "\copy test_formulary FROM '/data/test_formulary.txt' DELIMITER '|' CSV HEADER"

tar xvf /data/full_formulary.tar.gz -C /tmp
psql --username "$APP_DB_USER" --dbname "$APP_DB_NAME" \
  -c "\copy formulary FROM '/tmp/full_formulary.txt' DELIMITER '|' CSV HEADER"
