from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa
from pandas.testing import assert_frame_equal

from drug_formulary_tiers.db import Settings, create_engine, load_formulary
from drug_formulary_tiers.schema import require_table
from tests.helpers import ConnectionFactory

DATA = Path(__file__).parents[1] / "data"


def test_settings_default_to_the_docker_compose_database() -> None:
    assert Settings().url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://appuser:appuser@localhost:5432/formulary"
    )


def test_create_engine_prefers_explicit_url_then_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-env.db")

    assert create_engine("sqlite:///explicit.db").url.database == "explicit.db"
    assert create_engine().url.database == "from-env.db"

    monkeypatch.delenv("DATABASE_URL")
    assert create_engine().url == Settings().url


def test_load_formulary_returns_table_1(
    connect: ConnectionFactory, readme_formulary: pd.DataFrame
) -> None:
    with connect(readme_formulary) as connection:
        loaded = load_formulary(connection, "test_formulary")

    assert_frame_equal(loaded, readme_formulary)


def test_load_formulary_rejects_unknown_tables() -> None:
    with sa.create_engine("sqlite://").connect() as connection:
        with pytest.raises(ValueError, match="unknown table"):
            load_formulary(connection, "users")


def test_require_table_accepts_the_formulary_tables() -> None:
    assert require_table("formulary") == "formulary"
    assert require_table("test_formulary") == "test_formulary"


def test_test_data_file_is_the_readme_example(readme_formulary: pd.DataFrame) -> None:
    data = pd.read_csv(
        DATA / "test_formulary.txt", sep="|", dtype={"FORMULARY_ID": str, "RXCUI": str}
    ).rename(columns=str.lower)

    assert_frame_equal(data[readme_formulary.columns], readme_formulary)
