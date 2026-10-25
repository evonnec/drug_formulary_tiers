"""Both solutions agree with a brute-force reading of the README on random data."""

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pandas.testing import assert_frame_equal

from drug_formulary_tiers import pandas_solution, sql_solution
from tests.helpers import ConnectionFactory, formulary_frame
from tests.oracle import expected_tier_differences

FORMULARY_IDS = [f"{n:08d}" for n in range(1, 7)]
RXCUIS = [str(n) for n in range(1000, 1012)]


@st.composite
def formularies(draw: st.DrawFn) -> tuple[pd.DataFrame, str]:
    """A Table-1 with unique (formulary_id, rxcui) keys, and a target in it."""
    drugs = draw(
        st.dictionaries(
            st.tuples(st.sampled_from(FORMULARY_IDS), st.sampled_from(RXCUIS)),
            st.integers(min_value=1, max_value=6),
            min_size=1,
            max_size=40,
        )
    )
    rows = [
        (formulary_id, tier, rxcui) for (formulary_id, rxcui), tier in drugs.items()
    ]
    target_id = draw(st.sampled_from(sorted({row[0] for row in rows})))
    return formulary_frame(rows), target_id


def averages(table_3: pd.DataFrame) -> dict[str, float]:
    return dict(zip(table_3.formulary_id, table_3.tier_difference, strict=True))


@given(formularies())
def test_pandas_matches_reference(case: tuple[pd.DataFrame, str]) -> None:
    formulary, target_id = case
    expected_all, expected_changed = expected_tier_differences(
        formulary.itertuples(index=False, name=None), target_id
    )

    comparison = pandas_solution.build_comparison_table(formulary, target_id)
    all_tiers = pandas_solution.average_tier_difference(comparison)
    changed = pandas_solution.average_tier_difference(comparison, exclude_equal=True)

    assert averages(all_tiers) == pytest.approx(expected_all)
    assert averages(changed) == pytest.approx(expected_changed, nan_ok=True)


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(formularies())
def test_sql_matches_pandas_and_reference(
    connect: ConnectionFactory, case: tuple[pd.DataFrame, str]
) -> None:
    formulary, target_id = case
    expected_all, expected_changed = expected_tier_differences(
        formulary.itertuples(index=False, name=None), target_id
    )

    with connect(formulary) as connection:
        comparison = sql_solution.build_comparison_table(
            connection, "test_formulary", target_id
        )
        all_tiers = sql_solution.average_tier_difference(
            connection, "test_formulary", target_id
        )
        changed = sql_solution.average_tier_difference(
            connection, "test_formulary", target_id, exclude_equal=True
        )

    assert_frame_equal(
        comparison,
        pandas_solution.build_comparison_table(formulary, target_id),
        check_dtype=False,  # an empty SQL result has no rows to infer types from
    )
    assert averages(all_tiers) == pytest.approx(expected_all)
    assert averages(changed) == pytest.approx(expected_changed, nan_ok=True)
