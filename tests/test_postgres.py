"""Checks against the docker compose database as db/01-init.sh loads it.

Run with `docker compose up -d --wait` and
TEST_DATABASE_URL=postgresql+psycopg://appuser:appuser@localhost:5432/formulary
"""

from collections.abc import Iterator

import pandas as pd
import pytest
import sqlalchemy as sa
from pandas.testing import assert_frame_equal

from drug_formulary_tiers import pandas_solution, sql_solution
from drug_formulary_tiers.db import load_formulary
from tests.helpers import TEST_DATABASE_URL, requires_postgres
from tests.oracle import expected_tier_differences

pytestmark = [pytest.mark.postgres, requires_postgres]

FULL_TARGET = "00022170"


@pytest.fixture(scope="module")
def connection() -> Iterator[sa.Connection]:
    engine = sa.create_engine(TEST_DATABASE_URL or "")
    with engine.connect() as connection:
        yield connection
    engine.dispose()


@pytest.fixture(scope="module")
def full_formulary(connection: sa.Connection) -> pd.DataFrame:
    return load_formulary(connection, "formulary")


def test_test_formulary_is_the_readme_example(
    connection: sa.Connection, readme_formulary: pd.DataFrame
) -> None:
    loaded = load_formulary(connection, "test_formulary")

    assert_frame_equal(loaded, readme_formulary)


def test_full_formulary_is_loaded(full_formulary: pd.DataFrame) -> None:
    assert len(full_formulary) == 1_583_463
    assert full_formulary.formulary_id.nunique() == 458


@pytest.mark.parametrize("table", ["test_formulary", "formulary"])
def test_key_is_enforced(connection: sa.Connection, table: str) -> None:
    existing = connection.execute(
        sa.text(f"SELECT formulary_id, rxcui FROM {table} LIMIT 1")
    ).one()
    with pytest.raises(sa.exc.IntegrityError):
        connection.execute(
            sa.text(
                f"INSERT INTO {table} (formulary_id, tier_level_value, rxcui)"
                " VALUES (:formulary_id, 1, :rxcui)"
            ),
            existing._asdict(),
        )
    connection.rollback()


def test_full_formulary_solutions_agree_with_reference(
    connection: sa.Connection, full_formulary: pd.DataFrame
) -> None:
    expected_all, expected_changed = expected_tier_differences(
        full_formulary.itertuples(index=False, name=None), FULL_TARGET
    )
    comparison = pandas_solution.build_comparison_table(full_formulary, FULL_TARGET)
    results = {
        "pandas A": pandas_solution.average_tier_difference(comparison),
        "pandas B": pandas_solution.average_tier_difference(
            comparison, exclude_equal=True
        ),
        "sql A": sql_solution.average_tier_difference(
            connection, "formulary", FULL_TARGET
        ),
        "sql B": sql_solution.average_tier_difference(
            connection, "formulary", FULL_TARGET, exclude_equal=True
        ),
    }

    assert len(comparison) == 1_659_527
    for name, table_3 in results.items():
        expected = expected_changed if name.endswith("B") else expected_all
        actual = dict(zip(table_3.formulary_id, table_3.tier_difference, strict=True))
        assert actual == pytest.approx(expected, nan_ok=True), name


def test_full_formulary_comparison_tables_agree(
    connection: sa.Connection, full_formulary: pd.DataFrame
) -> None:
    assert_frame_equal(
        sql_solution.build_comparison_table(connection, "formulary", FULL_TARGET),
        pandas_solution.build_comparison_table(full_formulary, FULL_TARGET),
    )
