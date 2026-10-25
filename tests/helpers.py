"""Constants and helpers shared by the tests and their fixtures."""

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, cast

import pandas as pd
import pytest
import sqlalchemy as sa

from drug_formulary_tiers.schema import FORMULARY_TABLES, TABLE_3_COLUMNS

# The docker compose database, e.g.
# postgresql+psycopg://appuser:appuser@localhost:5432/formulary
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requires_postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to run against Postgres"
)

README_TARGET = "00019356"

type ConnectionFactory = Callable[[pd.DataFrame], AbstractContextManager[sa.Connection]]


def formulary_frame(rows: list[tuple[str, int, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["formulary_id", "tier_level_value", "rxcui"])


def table_3_frame(averages: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(averages.items(), columns=list(TABLE_3_COLUMNS))


@contextmanager
def formulary_connection(
    backend: str, formulary: pd.DataFrame
) -> Iterator[sa.Connection]:
    """A connection whose test_formulary and formulary tables hold `formulary`.

    The tables are temporary, which shadows any real tables of the same name for
    this connection only, so the docker compose database is left untouched.
    """
    url = TEST_DATABASE_URL if backend == "postgres" else "sqlite://"
    assert url is not None
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            for table in FORMULARY_TABLES:
                connection.execute(
                    sa.text(
                        f"CREATE TEMPORARY TABLE {table} (formulary_id TEXT NOT NULL,"
                        " tier_level_value INTEGER NOT NULL, rxcui TEXT NOT NULL)"
                    )
                )
                if len(formulary):
                    connection.execute(
                        sa.text(
                            f"INSERT INTO {table} (formulary_id, tier_level_value, rxcui)"
                            " VALUES (:formulary_id, :tier_level_value, :rxcui)"
                        ),
                        cast(list[dict[str, Any]], formulary.to_dict("records")),
                    )
            yield connection
    finally:
        engine.dispose()
