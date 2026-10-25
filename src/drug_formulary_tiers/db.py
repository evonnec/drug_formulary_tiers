"""Database connection settings and the Table-1 extract."""

import os
from dataclasses import dataclass

lazy import pandas as pd
lazy import sqlalchemy as sa

from drug_formulary_tiers.schema import TABLE_1_COLUMNS, require_table


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


def load_formulary(connection: sa.Connection, table: str) -> pd.DataFrame:
    """Table-1: the formulary_id, tier_level_value and rxcui of every row in `table`."""
    query = sa.select(
        sa.table(require_table(table), *(sa.column(c) for c in TABLE_1_COLUMNS))
    )
    return pd.read_sql_query(query, connection)
