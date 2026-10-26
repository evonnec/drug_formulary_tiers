import re
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest
import sqlalchemy as sa

from drug_formulary_tiers.cli import main
from tests.helpers import README_TARGET, create_formulary_table, formulary_frame

EXTRA_FORMULARY = "00019500"


@pytest.fixture
def database_url(tmp_path: Path, readme_formulary: pl.DataFrame) -> str:
    """A SQLite file with the README example in test_formulary, plus one more
    formulary in formulary, so a part reading the wrong table shows up."""
    url = f"sqlite:///{tmp_path / 'formulary.db'}"
    engine = sa.create_engine(url)
    extra = formulary_frame([(EXTRA_FORMULARY, 4, "1001")])
    with engine.begin() as connection:
        create_formulary_table(connection, "test_formulary", readme_formulary)
        create_formulary_table(
            connection, "formulary", pl.concat([readme_formulary, extra])
        )
    engine.dispose()
    return url


def table_3_values(output: str, heading: str) -> dict[str, float]:
    section = output.split(heading, 1)[1].split("\n\n", 1)[0]
    return {
        formulary_id: float(value)
        for formulary_id, value in re.findall(r"(\d{8})\s+┆\s+(-?\d+\.\d+)", section)
    }


@pytest.mark.parametrize(("part", "method"), [("1", "polars"), ("2", "sql")])
def test_parts_1_and_2_print_the_readme_results(
    database_url: str, capsys: pytest.CaptureFixture[str], part: str, method: str
) -> None:
    assert main([part, "--database-url", database_url]) == 0

    out = capsys.readouterr().out
    assert (
        f"== Part {part} with {method}: test_formulary, target {README_TARGET}" in out
    )
    assert "Table-2:\nshape: (17, 5)" in out
    assert table_3_values(out, "Table-3 (A)") == {
        "00019100": 0.0,
        "00019200": 0.0,
        "00019300": -1.0,
        "00019400": 0.0,
    }
    assert table_3_values(out, "Table-3 (B)")["00019300"] == -1.5
    assert EXTRA_FORMULARY not in out
    assert re.search(r"Execution time: \d+\.\d\ds \(.*Table-3", out)


def test_part_3_runs_both_methods_on_formulary(
    database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["3", "--target", README_TARGET, "--database-url", database_url]) == 0

    out = capsys.readouterr().out
    assert "== Part 3 with polars: formulary" in out
    assert "== Part 3 with sql: formulary" in out
    assert out.count("Execution time:") == 2
    # Part 3 needs only the averages, so SQL skips fetching Table-2
    polars_out, sql_out = out.split("== Part 3 with sql", 1)
    assert "Table-2:" in polars_out
    assert "Table-2" not in sql_out
    for heading in ("Table-3 (A)", "Table-3 (B)"):
        assert out.count(heading) == 2
        assert EXTRA_FORMULARY in table_3_values(out, heading)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        # Part 3 defaults to 00022170, which is not in the README example
        (["3"], "target formulary_id '00022170' not found in formulary"),
        (["1", "--target", ""], "target formulary_id '' not found in test_formulary"),
    ],
)
def test_missing_target_exits_with_an_error(
    database_url: str,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    message: str,
) -> None:
    assert main([*argv, "--database-url", database_url]) == 1
    assert message in capsys.readouterr().err


def test_unreachable_database_exits_with_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    url = f"sqlite:///{tmp_path / 'missing' / 'formulary.db'}"

    assert main(["2", "--database-url", url]) == 1

    err = capsys.readouterr().err
    assert err.startswith("formulary-tiers: error: database error:")
    assert "Traceback" not in err


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("not a url", "Could not parse"),
        ("nosuchdialect://user:secret@localhost/db", "Can't load plugin"),
        ("mysql://user:secret@localhost/db", "No module named"),
    ],
    ids=["unparseable", "unknown dialect", "driver not installed"],
)
def test_unusable_database_url_exits_with_an_error(
    capsys: pytest.CaptureFixture[str], url: str, reason: str
) -> None:
    assert main(["1", "--database-url", url]) == 1

    err = capsys.readouterr().err
    assert err.startswith("formulary-tiers: error: cannot use the database URL:")
    assert reason in err
    assert "Traceback" not in err
    assert "secret" not in err


def test_database_url_defaults_to_the_environment(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert main(["1"]) == 0
    assert "Table-3 (A)" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["4"], ["one"]])
def test_invalid_part_is_a_usage_error(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(argv)
    assert exit_info.value.code == 2


def test_runs_as_a_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "drug_formulary_tiers", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "usage: formulary-tiers" in result.stdout
