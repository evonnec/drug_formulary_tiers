"""Shared fixtures: the README's worked example and per-backend connections."""

import os
from functools import partial

import polars as pl
import pytest

from drug_formulary_tiers.schema import TABLE_2_SCHEMA, polars_schema
from tests.helpers import (
    README_TARGET,
    TEST_DATABASE_URL,
    ConnectionFactory,
    formulary_connection,
    formulary_frame,
    requires_postgres,
    table_3_frame,
)


def pytest_configure(config: pytest.Config) -> None:
    # GitHub Actions sets CI; skipping the Postgres tests there would hide failures.
    if os.environ.get("CI") and not TEST_DATABASE_URL:
        raise pytest.UsageError("set TEST_DATABASE_URL in CI so the Postgres tests run")


@pytest.fixture
def readme_formulary() -> pl.DataFrame:
    """Table-1 from the README."""
    return formulary_frame(
        [
            ("00019356", 1, "1001"),
            ("00019356", 2, "1002"),
            ("00019356", 3, "1003"),
            ("00019100", 2, "1001"),
            ("00019100", 1, "1002"),
            ("00019100", 3, "1004"),
            ("00019200", 3, "1001"),
            ("00019200", 1, "1002"),
            ("00019200", 2, "1005"),
            ("00019300", 3, "1001"),
            ("00019300", 3, "1002"),
            ("00019300", 3, "1003"),
            ("00019400", 1, "1004"),
            ("00019400", 2, "1005"),
            ("00019400", 3, "1006"),
        ]
    )


@pytest.fixture
def readme_comparison() -> pl.DataFrame:
    """Table-2 from the README."""
    rows = [
        (1, "1001", "00019100", 2),
        (2, "1002", "00019100", 1),
        (3, "1003", "00019100", 7),
        (7, "1004", "00019100", 3),
        (1, "1001", "00019200", 3),
        (2, "1002", "00019200", 1),
        (3, "1003", "00019200", 7),
        (7, "1005", "00019200", 2),
        (1, "1001", "00019300", 3),
        (2, "1002", "00019300", 3),
        (3, "1003", "00019300", 3),
        (1, "1001", "00019400", 7),
        (2, "1002", "00019400", 7),
        (3, "1003", "00019400", 7),
        (7, "1004", "00019400", 1),
        (7, "1005", "00019400", 2),
        (7, "1006", "00019400", 3),
    ]
    return pl.DataFrame(
        [(README_TARGET, *row) for row in rows],
        schema=polars_schema(TABLE_2_SCHEMA),
        orient="row",
    )


@pytest.fixture
def readme_all_tiers() -> pl.DataFrame:
    """Table-3 (A) for the README example, worked out by hand from Table-2."""
    return table_3_frame(
        {"00019100": 0.0, "00019200": 0.0, "00019300": -1.0, "00019400": 0.0}
    )


@pytest.fixture
def readme_changed_tiers() -> pl.DataFrame:
    """Table-3 (B): 00019300 averages -1 and -2 once its matching 1003 is left out."""
    return table_3_frame(
        {"00019100": 0.0, "00019200": 0.0, "00019300": -1.5, "00019400": 0.0}
    )


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param("postgres", marks=[pytest.mark.postgres, requires_postgres]),
    ]
)
def connect(request: pytest.FixtureRequest) -> ConnectionFactory:
    """Open a connection loaded with a formulary, once per database backend."""
    return partial(formulary_connection, request.param)
