"""Both solutions agree with a brute-force reading of the README on random data."""

import logging
import math

import polars as pl
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from polars.testing import assert_frame_equal

from drug_formulary_tiers import polars_solution
from drug_formulary_tiers.sql_solution import SqlComparison
from tests.helpers import ConnectionFactory, formulary_frame
from tests.oracle import expected_tier_differences

# Mixed case, punctuation and non-ASCII ids check that both solutions sort the
# same way, and quotes, commas, newlines and NULL-like text check the CSV that
# Postgres sends Table-2 over. Tier 7 also appears in the real data.
FORMULARY_IDS = [*(f"{n:08d}" for n in range(1, 9)), "B", "_x", "a", "Ä", 'a"b', "NULL"]
RXCUIS = [
    *(str(n) for n in range(1000, 1012)),
    "999",
    "Rx",
    "é",
    "c,d",
    "a\nb",
    "\\N",
    " x ",
    "",
]


@st.composite
def formularies(draw: st.DrawFn) -> tuple[pl.DataFrame, str]:
    """A Table-1 with unique (formulary_id, rxcui) keys, and a target in it."""
    drugs = draw(
        st.dictionaries(
            st.tuples(st.sampled_from(FORMULARY_IDS), st.sampled_from(RXCUIS)),
            st.integers(min_value=1, max_value=7),
            min_size=1,
            max_size=60,
        )
    )
    rows = [
        (formulary_id, tier, rxcui) for (formulary_id, rxcui), tier in drugs.items()
    ]
    target_id = draw(st.sampled_from(sorted({row[0] for row in rows})))
    return formulary_frame(rows), target_id


def averages(table_3: pl.DataFrame) -> dict[str, float]:
    return {
        formulary_id: math.nan if average is None else average
        for formulary_id, average in table_3.iter_rows()
    }


@pytest.fixture(autouse=True)
def quiet_tier_warnings(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="drug_formulary_tiers")


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(formularies())
def test_polars_matches_reference(case: tuple[pl.DataFrame, str]) -> None:
    formulary, target_id = case
    expected_all, expected_changed = expected_tier_differences(
        formulary.iter_rows(), target_id
    )

    comparison = polars_solution.build_comparison_table(formulary, target_id)
    all_tiers = polars_solution.average_tier_difference(comparison)
    changed = polars_solution.average_tier_difference(comparison, exclude_equal=True)

    assert averages(all_tiers) == pytest.approx(expected_all, rel=1e-12)
    assert averages(changed) == pytest.approx(expected_changed, rel=1e-12, nan_ok=True)


@settings(
    max_examples=50,
    deadline=None,  # each example opens its own database connection
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(formularies())
def test_sql_matches_polars_and_reference(
    connect: ConnectionFactory, case: tuple[pl.DataFrame, str]
) -> None:
    formulary, target_id = case
    expected_all, expected_changed = expected_tier_differences(
        formulary.iter_rows(), target_id
    )

    with connect(formulary) as connection:
        query = SqlComparison(connection, "test_formulary", target_id)
        comparison = query.comparison_table()
        all_tiers = query.average_tier_difference()
        changed = query.average_tier_difference(exclude_equal=True)

    assert_frame_equal(
        comparison, polars_solution.build_comparison_table(formulary, target_id)
    )
    assert averages(all_tiers) == pytest.approx(expected_all, rel=1e-12)
    assert averages(changed) == pytest.approx(expected_changed, rel=1e-12, nan_ok=True)
