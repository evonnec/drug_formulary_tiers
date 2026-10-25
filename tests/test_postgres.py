"""Checks against the docker compose database as db/01-init.sh loads it.

Run with `docker compose up -d --wait` and
TEST_DATABASE_URL=postgresql+psycopg://appuser:appuser@localhost:5432/formulary
"""

from collections.abc import Iterator
from fractions import Fraction

import polars as pl
import pytest
import sqlalchemy as sa
from polars.testing import assert_frame_equal

from drug_formulary_tiers import polars_solution
from drug_formulary_tiers.db import load_formulary
from drug_formulary_tiers.sql_solution import SqlComparison, _has_unique_key
from tests.helpers import TEST_DATABASE_URL, requires_postgres
from tests.oracle import expected_tier_differences

pytestmark = [pytest.mark.postgres, requires_postgres]

FULL_TARGET = "00022170"

# Exact averages for a few formularies against 00022170, computed independently
# with fractions from data/full_formulary.tar.gz. Three formularies match the
# target exactly, so part B has nothing to average for them.
GOLDEN = {
    "00022000": (Fraction(397, 134), Fraction(10719, 3443)),
    "00022001": (Fraction(1566, 1853), Fraction(9, 5)),
    "00022158": (Fraction(6299, 3904), Fraction(6299, 2821)),
    "00022153": (Fraction(0), None),
    "00022258": (Fraction(0), None),
    "00022360": (Fraction(0), None),
}


@pytest.fixture(scope="module")
def connection() -> Iterator[sa.Connection]:
    engine = sa.create_engine(TEST_DATABASE_URL or "")
    with engine.connect() as connection:
        yield connection
    engine.dispose()


@pytest.fixture(scope="module")
def full_formulary(connection: sa.Connection) -> pl.DataFrame:
    return load_formulary(connection, "formulary")


@pytest.fixture(scope="module")
def full_comparison(full_formulary: pl.DataFrame) -> pl.DataFrame:
    return polars_solution.build_comparison_table(full_formulary, FULL_TARGET)


@pytest.fixture(scope="module")
def full_sql(connection: sa.Connection) -> SqlComparison:
    return SqlComparison(connection, "formulary", FULL_TARGET)


def test_test_formulary_is_the_readme_example(
    connection: sa.Connection, readme_formulary: pl.DataFrame
) -> None:
    assert_frame_equal(load_formulary(connection, "test_formulary"), readme_formulary)


def test_full_formulary_is_loaded(full_formulary: pl.DataFrame) -> None:
    assert full_formulary.height == 1_583_463
    assert full_formulary["formulary_id"].n_unique() == 458


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


def test_primary_key_lets_the_check_skip_counting_duplicates(
    connection: sa.Connection,
) -> None:
    assert _has_unique_key(connection, "formulary")
    assert _has_unique_key(connection, "test_formulary")


def test_key_columns_use_c_collation(connection: sa.Connection) -> None:
    collations = connection.execute(
        sa.text(
            "SELECT table_name, column_name, collation_name"
            " FROM information_schema.columns"
            " WHERE column_name IN ('formulary_id', 'rxcui')"
            " AND table_schema = 'public'"
        )
    ).all()

    assert len(collations) == 4
    assert {row.collation_name for row in collations} == {"C"}


def test_app_user_owns_its_tables_without_superuser(connection: sa.Connection) -> None:
    role = connection.execute(
        sa.text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    ).scalar_one()
    owners = connection.execute(
        sa.text(
            "SELECT DISTINCT tableowner = current_user FROM pg_tables"
            " WHERE tablename IN ('formulary', 'test_formulary')"
        )
    ).scalars()

    assert role is False
    assert list(owners) == [True]


def test_full_comparison_size(full_comparison: pl.DataFrame) -> None:
    assert full_comparison.height == 1_659_527
    assert full_comparison["formulary_id"].n_unique() == 457


@pytest.mark.parametrize("method", ["polars", "sql"])
def test_full_formulary_matches_golden_values(
    full_comparison: pl.DataFrame, full_sql: SqlComparison, method: str
) -> None:
    if method == "polars":
        all_tiers = polars_solution.average_tier_difference(full_comparison)
        changed = polars_solution.average_tier_difference(
            full_comparison, exclude_equal=True
        )
    else:
        all_tiers = full_sql.average_tier_difference()
        changed = full_sql.average_tier_difference(exclude_equal=True)
    actual_all, actual_changed = dict(all_tiers.iter_rows()), dict(changed.iter_rows())

    for formulary_id, (expected_all, expected_changed) in GOLDEN.items():
        assert actual_all[formulary_id] == pytest.approx(float(expected_all), abs=1e-12)
        if expected_changed is None:
            assert actual_changed[formulary_id] is None
        else:
            assert actual_changed[formulary_id] == pytest.approx(
                float(expected_changed), abs=1e-12
            )


def test_full_formulary_solutions_agree_with_reference(
    full_formulary: pl.DataFrame,
    full_comparison: pl.DataFrame,
    full_sql: SqlComparison,
) -> None:
    expected_all, expected_changed = expected_tier_differences(
        full_formulary.iter_rows(), FULL_TARGET
    )
    results = {
        "polars A": polars_solution.average_tier_difference(full_comparison),
        "polars B": polars_solution.average_tier_difference(
            full_comparison, exclude_equal=True
        ),
        "sql A": full_sql.average_tier_difference(),
        "sql B": full_sql.average_tier_difference(exclude_equal=True),
    }

    for name, table_3 in results.items():
        expected = expected_changed if name.endswith("B") else expected_all
        actual = {
            formulary_id: float("nan") if average is None else average
            for formulary_id, average in table_3.iter_rows()
        }
        assert actual == pytest.approx(expected, abs=1e-12, nan_ok=True), name


def test_full_formulary_comparison_tables_agree(
    full_comparison: pl.DataFrame, full_sql: SqlComparison
) -> None:
    assert_frame_equal(full_sql.comparison_table(), full_comparison)
