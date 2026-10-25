from dataclasses import dataclass

lazy import pandas as pd
lazy import sqlalchemy as sa


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
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


def get_connection(settings: Settings) -> sa.Connection:
    """Create a connection to the database."""
    engine = sa.create_engine(settings.url, pool_recycle=3600)
    return engine.connect()


def get_test_data(db_connection: sa.Connection) -> pd.DataFrame:
    """Test function to confirm access to the data in the database."""
    return pd.read_sql(sa.text("select * from test_formulary limit 10;"), db_connection)
