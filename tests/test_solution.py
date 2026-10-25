from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa

import solution
from connection import Settings, get_test_data

TEST_DATA = Path(__file__).parents[1] / "data" / "test_formulary.txt"
TARGET = "00019356"


@pytest.fixture
def engine() -> Iterator[sa.Engine]:
    """In-memory stand-in for the Postgres container, loaded from the test data."""
    engine = sa.create_engine("sqlite://")
    df = pd.read_csv(TEST_DATA, sep="|", dtype={"FORMULARY_ID": str, "RXCUI": str})
    df.columns = df.columns.str.lower()
    df.to_sql("test_formulary", engine, index=False)
    df.to_sql("formulary", engine, index=False)
    yield engine
    engine.dispose()


@pytest.fixture
def formulary(engine: sa.Engine) -> pd.DataFrame:
    return solution.load_table_into_dataframe(
        "test_formulary", engine, solution.COLUMNS
    )


def test_load_table_into_dataframe(formulary: pd.DataFrame) -> None:
    assert list(formulary.columns) == list(solution.COLUMNS)
    assert len(formulary) == 15
    assert formulary.formulary_id.nunique() == 5


def test_join_self_tables_without_condition(formulary: pd.DataFrame) -> None:
    joined = solution.join_self_tables(formulary, col="rxcui")

    # every pair of formularies sharing an rxcui, in both directions
    assert set(joined.columns) == {
        "formulary_id_target",
        "tier_level_value_target",
        "rxcui",
        "formulary_id",
        "tier_level_value",
    }
    assert len(joined) == 45


def test_join_self_tables_with_condition(formulary: pd.DataFrame) -> None:
    joined = solution.join_self_tables(formulary, col="rxcui", condition=TARGET)

    assert (joined.formulary_id == TARGET).all()
    assert set(joined.rxcui) == {"1001", "1002", "1003"}
    assert len(joined) == 10


def test_add_tier_difference() -> None:
    df = pd.DataFrame({"tier_level_value_target": [1, 3], "tier_level_value": [2, 3]})

    assert solution.add_tier_difference(df).tier_difference.tolist() == [-1, 0]
    assert "tier_difference" not in df.columns


def test_drop_unchanged_tiers() -> None:
    df = pd.DataFrame({"tier_difference": [-1, 0, 2]})

    assert solution.drop_unchanged_tiers(df).tier_difference.tolist() == [-1, 2]


def test_average_tier_difference(formulary: pd.DataFrame) -> None:
    table = solution.add_tier_difference(
        solution.join_self_tables(formulary, col="rxcui", condition=TARGET)
    ).drop(columns=solution.DROPPED_COLUMNS)

    all_tiers = solution.average_tier_difference(table)
    changed_tiers = solution.average_tier_difference(
        solution.drop_unchanged_tiers(table)
    )

    assert all_tiers.loc[TARGET, "tier_difference"] == pytest.approx(0.4)
    assert changed_tiers.loc[TARGET, "tier_difference"] == pytest.approx(2 / 3)


@pytest.mark.parametrize(("argv", "expected"), [([], None), ([TARGET], TARGET)])
def test_parse_args(argv: list[str], expected: str | None) -> None:
    assert solution.parse_args(argv).formulary_id == expected


@pytest.mark.parametrize(("argv", "part"), [([], "Part 1:"), ([TARGET], "Part 3:")])
def test_main(
    engine: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    part: str,
) -> None:
    monkeypatch.setattr(solution, "connect_to_db", lambda: engine)

    solution.main(argv)

    out = capsys.readouterr().out
    assert part in out
    assert "Table-3 for A:" in out
    assert "Table-3 for B:" in out
    assert "Execution time:" in out


def test_settings_url() -> None:
    url = Settings(host="db", port=5433).url

    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://appuser:appuser@db:5433/formulary"
    )


def test_get_test_data(engine: sa.Engine) -> None:
    with engine.connect() as connection:
        assert len(get_test_data(connection)) == 10
