"""Database connection settings and the Table-1 extract."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

lazy import polars as pl
lazy import sqlalchemy as sa

from drug_formulary_tiers.schema import TABLE_1_SCHEMA, polars_schema, require_table


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """The database started by `docker compose up`."""

    username: str = "appuser"
    password: str = "appuser"
    host: str = "localhost"
    port: int = 5432
    database_name: str = "formulary"

    @property
    def url(self) -> sa.URL:
        return sa.URL.create(
            "postgresql+psycopg",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database_name,
        )


def create_engine(url: str | sa.URL | None = None) -> sa.Engine:
    """Engine for `url`, else $DATABASE_URL, else the docker compose database."""
    return sa.create_engine(url or os.environ.get("DATABASE_URL") or Settings().url)


# Rows fetched into Python objects at a time; polars converts each batch before
# the next is fetched, so peak memory stays a fraction of fetching every row.
_BATCH_SIZE = 50_000


def read_frame(
    connection: sa.Connection,
    query: sa.TextClause | sa.Selectable,
    schema: Mapping[str, type],
    parameters: Mapping[str, Any] | None = None,
) -> pl.DataFrame:
    """The rows of `query`, executed through SQLAlchemy, as a DataFrame of `schema`."""
    batches = list(
        pl.read_database(
            query,
            connection,
            iter_batches=True,
            batch_size=_BATCH_SIZE,
            execute_options={"parameters": parameters} if parameters else None,
            schema_overrides=polars_schema(schema),
        )
    )
    if not batches:
        return pl.DataFrame(schema=polars_schema(schema))
    return pl.concat(batches).select(*schema)


def load_formulary(connection: sa.Connection, table: str) -> pl.DataFrame:
    """Table-1: the formulary_id, tier_level_value and rxcui of every row in `table`."""
    query = sa.select(
        sa.table(require_table(table), *(sa.column(c) for c in TABLE_1_SCHEMA))
    )
    return read_frame(connection, query, TABLE_1_SCHEMA)
