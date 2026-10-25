import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa

from drug_formulary_tiers.cli import main
from drug_formulary_tiers.schema import FORMULARY_TABLES
from tests.helpers import README_TARGET


@pytest.fixture
def database_url(tmp_path: Path, readme_formulary: pd.DataFrame) -> str:
    """A SQLite file holding the README example in both formulary tables."""
    url = f"sqlite:///{tmp_path / 'formulary.db'}"
    engine = sa.create_engine(url)
    for table in FORMULARY_TABLES:
        readme_formulary.to_sql(table, engine, index=False)
    engine.dispose()
    return url


def table_3_values(output: str, heading: str) -> dict[str, float]:
    section = output.split(heading, 1)[1].split("\n\n", 1)[0]
    return {
        formulary_id: float(value)
        for formulary_id, value in re.findall(r"(\d{8})\s+(-?\d+\.\d+)", section)
    }


@pytest.mark.parametrize(("part", "method"), [("1", "pandas"), ("2", "sql")])
def test_parts_1_and_2_print_the_readme_results(
    database_url: str, capsys: pytest.CaptureFixture[str], part: str, method: str
) -> None:
    assert main([part, "--database-url", database_url]) == 0

    out = capsys.readouterr().out
    assert (
        f"== Part {part} with {method}: test_formulary, target {README_TARGET}" in out
    )
    assert table_3_values(out, "Table-3 (A)") == {
        "00019100": 0.0,
        "00019200": 0.0,
        "00019300": -1.0,
        "00019400": 0.0,
    }
    assert table_3_values(out, "Table-3 (B)")["00019300"] == -1.5
    assert re.search(r"Execution time: \d+\.\d\ds \(.*Table-3", out)


def test_part_3_runs_both_methods_with_timings(
    database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["3", "--target", README_TARGET, "--database-url", database_url]) == 0

    out = capsys.readouterr().out
    assert "== Part 3 with pandas: formulary" in out
    assert "== Part 3 with sql: formulary" in out
    assert out.count("Execution time:") == 2


def test_missing_target_exits_with_an_error(
    database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # Part 3 defaults to 00022170, which is not in the README example
    assert main(["3", "--database-url", database_url]) == 1

    err = capsys.readouterr().err
    assert "target formulary_id '00022170' not found in formulary" in err


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
