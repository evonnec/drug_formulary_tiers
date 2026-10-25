"""Constants and helpers shared by the tests and their fixtures."""

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import polars as pl
import pytest
import sqlalchemy as sa

from drug_formulary_tiers.schema import (
    TABLE_1_SCHEMA,
    TABLE_3_SCHEMA,
    polars_schema,
)

# The docker compose database, e.g.
# postgresql+psycopg://appuser:appuser@localhost:5432/formulary
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requires_postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to run against Postgres"
)

README_TARGET = "00019356"

type ConnectionFactory = Callable[..., AbstractContextManager[sa.Connection]]


def formulary_frame(rows: list[tuple[str, int, str]]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=polars_schema(TABLE_1_SCHEMA), orient="row")


def table_3_frame(averages: dict[str, float | None]) -> pl.DataFrame:
    return pl.DataFrame(
        list(averages.items()), schema=polars_schema(TABLE_3_SCHEMA), orient="row"
    )


def create_formulary_table(
    connection: sa.Connection,
    table: str,
    formulary: pl.DataFrame,
    *,
    temporary: bool = False,
    constraints: str = "NOT NULL",
) -> None:
    """Create `table` holding `formulary`, keyed like db/01-init.sh by default.

    Pass `constraints=""` to build a table the database won't protect, as a
    database not set up by db/01-init.sh might be.
    """
    collate = ' COLLATE "C"' if connection.dialect.name == "postgresql" else ""
    connection.execute(
        sa.text(
            f"CREATE {'TEMPORARY ' if temporary else ''}TABLE {table} ("
            f"formulary_id TEXT{collate} {constraints},"
            f" tier_level_value INTEGER {constraints},"
            f" rxcui TEXT{collate} {constraints})"
        )
    )
    if not formulary.is_empty():
        connection.execute(
            sa.text(
                f"INSERT INTO {table} (formulary_id, tier_level_value, rxcui)"
                " VALUES (:formulary_id, :tier_level_value, :rxcui)"
            ),
            formulary.to_dicts(),
        )


@contextmanager
def formulary_connection(
    backend: str,
    test_formulary: pl.DataFrame,
    formulary: pl.DataFrame | None = None,
    *,
    constraints: str = "NOT NULL",
) -> Iterator[sa.Connection]:
    """A connection whose test_formulary and formulary tables hold the given rows.

    `formulary` defaults to `test_formulary`. The tables are temporary, which
    shadows any real tables of the same name for this connection only, so the
    docker compose database is left untouched.
    """
    url = TEST_DATABASE_URL if backend == "postgres" else "sqlite://"
    assert url is not None
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            for table, rows in [
                ("test_formulary", test_formulary),
                ("formulary", test_formulary if formulary is None else formulary),
            ]:
                create_formulary_table(
                    connection, table, rows, temporary=True, constraints=constraints
                )
            yield connection
    finally:
        engine.dispose()
