"""The database connection and the Table-1 extract."""

import io
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, cast

lazy import polars as pl
lazy import psycopg
lazy import sqlalchemy as sa

from drug_formulary_tiers.schema import TABLE_1_SCHEMA, polars_schema, require_table


def create_engine(url: str | sa.URL | None = None) -> sa.Engine:
    """Engine for `url`, else $DATABASE_URL (see .env.example)."""
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise sa.exc.ArgumentError(
            "none given; pass --database-url or set DATABASE_URL (see .env.example)"
        )
    return sa.create_engine(url)


@contextmanager
def snapshot(engine: sa.Engine) -> Iterator[sa.Connection]:
    """A connection whose queries all read the same snapshot of the data.

    On Postgres that is one REPEATABLE READ, READ ONLY transaction, so the SQL
    check, Table-2 and Table-3 can't disagree if a table changes mid-run. The
    transaction starts at the first query and is rolled back on exit.
    """
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
        yield connection


def read_frame(
    connection: sa.Connection,
    query: sa.TextClause | sa.Selectable,
    schema: Mapping[str, type],
    parameters: Mapping[str, Any] | None = None,
) -> pl.DataFrame:
    """The rows of `query`, whose columns are those of `schema`, as a DataFrame.

    On psycopg the rows come over COPY as CSV, which polars parses without
    building a Python object per value: several times less memory than
    fetching rows, and faster. Other drivers, such as SQLite's, fetch rows.
    """
    if connection.dialect.driver != "psycopg":
        return pl.read_database(
            query,
            connection,
            execute_options={"parameters": parameters} if parameters else None,
            schema_overrides=polars_schema(schema),
        )
    compiled = query.compile(dialect=connection.dialect)
    statement = f"COPY ({compiled}) TO STDOUT (FORMAT csv, HEADER, ENCODING 'UTF8')"
    params = compiled.construct_params(parameters) or None
    data = bytearray()
    try:
        driver = cast(
            "psycopg.Connection[Any]", connection.connection.driver_connection
        )
        with driver.cursor() as cursor:
            with cursor.copy(statement, params) as copy:
                # libpq hands over one row per block
                for block in copy:
                    data += block
    except psycopg.Error as error:
        # The failed COPY aborted the transaction behind SQLAlchemy's back.
        connection.rollback()
        raise sa.exc.DBAPIError.instance(
            statement, params, error, psycopg.Error
        ) from error
    return pl.read_csv(io.BytesIO(data), schema_overrides=polars_schema(schema)).select(
        *schema
    )


def load_formulary(connection: sa.Connection, table: str) -> pl.DataFrame:
    """Table-1: the formulary_id, tier_level_value and rxcui of every row in `table`."""
    query = sa.select(
        sa.table(require_table(table), *(sa.column(c) for c in TABLE_1_SCHEMA))
    )
    return read_frame(connection, query, TABLE_1_SCHEMA)
