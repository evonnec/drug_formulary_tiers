"""Part 2: the same comparison with every join and aggregate done in SQL."""

lazy import polars as pl
lazy import sqlalchemy as sa

from drug_formulary_tiers.db import read_frame
from drug_formulary_tiers.schema import (
    COVERED_TIERS,
    KEY,
    TABLE_2_SCHEMA,
    TABLE_3_SCHEMA,
    UNCOVERED_TIER,
    TargetNotFoundError,
    check_counts,
    polars_schema,
    require_table,
)

# Table-2 as a CTE. The table name is checked against FORMULARY_TABLES before it
# is formatted in; the target formulary_id is always a bind parameter.
_COMPARISON_CTE = """
WITH target AS (
    SELECT rxcui, tier_level_value
    FROM {table}
    WHERE formulary_id = :target_id
),
others AS (
    SELECT formulary_id, rxcui, tier_level_value
    FROM {table}
    WHERE formulary_id <> :target_id
),
-- Every other formulary paired with every target drug, so a drug the formulary
-- lacks still gets a row; the full join then adds the drugs the target lacks.
target_drugs AS (
    SELECT f.formulary_id, t.rxcui, t.tier_level_value
    FROM (
        SELECT DISTINCT formulary_id FROM {table} WHERE formulary_id <> :target_id
    ) AS f
    CROSS JOIN target AS t
),
comparison AS (
    SELECT
        CAST(:target_id AS TEXT) AS formulary_target_id,
        COALESCE(d.tier_level_value, {uncovered}) AS tier_level_value_target,
        COALESCE(d.rxcui, o.rxcui) AS rxcui,
        COALESCE(d.formulary_id, o.formulary_id) AS formulary_id,
        COALESCE(o.tier_level_value, {uncovered}) AS tier_level_value
    FROM target_drugs AS d
    FULL OUTER JOIN others AS o
        ON o.formulary_id = d.formulary_id AND o.rxcui = d.rxcui
)
"""

# Sorted by polars once fetched rather than by ORDER BY: Postgres spends longer
# sorting the 1.7M rows than joining them, and polars sorts in byte order
# whatever the columns' collation.
_TABLE_2_SQL = """
SELECT * FROM comparison
"""

# Table-3 (A) and (B) in one pass, without building Table-2. On the union of a
# formulary's drugs and the target's, with 7 for a missing drug, the differences
# sum to sum(target tier - 7) + sum(7 - formulary tier) whatever drugs they
# share, so only the counts need the target's tiers. Joining each drug to the
# target's few thousand keeps the hash table small, where Table-2's full join
# spills to disk. A formulary whose drugs all match the target has no changed
# drugs, so NULLIF leaves it a NULL (B) average.
_TABLE_3_SQL = """
WITH target_totals AS (
    SELECT
        count(*) AS drugs,
        COALESCE(SUM(tier_level_value - {uncovered}), 0) AS difference,
        count(CASE WHEN tier_level_value <> {uncovered} THEN 1 END) AS changed
    FROM {table}
    WHERE formulary_id = :target_id
),
per_formulary AS (
    SELECT
        o.formulary_id,
        count(*) AS drugs,
        SUM({uncovered} - o.tier_level_value) AS difference,
        count(CASE WHEN COALESCE(t.tier_level_value, {uncovered}) <> o.tier_level_value
            THEN 1 END) AS changed,
        count(t.rxcui) AS shared_drugs,
        count(CASE WHEN t.tier_level_value <> {uncovered} THEN 1 END) AS shared_changed
    FROM {table} AS o
    LEFT JOIN {table} AS t
        ON t.formulary_id = :target_id AND t.rxcui = o.rxcui
    WHERE o.formulary_id <> :target_id
    GROUP BY o.formulary_id
)
SELECT
    p.formulary_id,
    CAST(p.difference + tt.difference AS DOUBLE PRECISION)
        / (p.drugs + tt.drugs - p.shared_drugs) AS all_tiers,
    CAST(p.difference + tt.difference AS DOUBLE PRECISION)
        / NULLIF(p.changed + tt.changed - p.shared_changed, 0) AS changed_tiers
FROM per_formulary AS p
CROSS JOIN target_totals AS tt
ORDER BY p.formulary_id
"""
_AVERAGES_SCHEMA = frozendict(
    {"formulary_id": str, "all_tiers": float, "changed_tiers": float}
)


def _comparison_query(table: str, select: str) -> sa.TextClause:
    cte = _COMPARISON_CTE.format(table=require_table(table), uncovered=UNCOVERED_TIER)
    return sa.text(cte + select)


# The same checks the polars solution makes on Table-1. The primary key in
# db/01-init.sh already rules out nulls and duplicates there, but other databases
# (or tables built some other way) may not.
_CHECK_SQL = """
SELECT
    {duplicate_keys} AS duplicate_keys,
    3 * count(*) - count(formulary_id) - count(tier_level_value) - count(rxcui)
        AS nulls,
    count(CASE WHEN tier_level_value NOT BETWEEN {low} AND {high} THEN 1 END)
        AS outside_tiers,
    count(CASE WHEN formulary_id = :target_id THEN 1 END) AS target_rows
FROM {table}
"""
_DUPLICATE_KEYS_SQL = """(SELECT count(*) FROM (
        SELECT 1 FROM {table} GROUP BY formulary_id, rxcui HAVING count(*) > 1
    ) AS duplicates)"""

# Counting duplicate keys is most of the check, and Postgres already rules them
# out with a unique index on (formulary_id, rxcui) or part of it, such as the
# primary key. Nulls are still counted, since a unique index allows them.
# to_regclass resolves the table name as the queries do, so a temporary table
# that shadows a keyed one is checked in full.
_UNIQUE_KEY_SQL = """
SELECT EXISTS (
    SELECT FROM pg_index
    WHERE indrelid = to_regclass(:table)
        AND indisunique AND indisvalid AND indimmediate AND indpred IS NULL
        AND indkey::int2[] <@ ARRAY(
            SELECT attnum FROM pg_attribute
            WHERE attrelid = to_regclass(:table)
                AND attname IN ('formulary_id', 'rxcui')
        )
)
"""


def _has_unique_key(connection: sa.Connection, table: str) -> bool:
    if connection.dialect.name != "postgresql":
        return False
    return bool(
        connection.execute(sa.text(_UNIQUE_KEY_SQL), {"table": table}).scalar_one()
    )


class SqlComparison:
    """Table-2 and Table-3 against one target, computed in the database.

    The table is checked once, when this is created, with the same rules as
    `polars_solution.build_comparison_table`.
    """

    def __init__(self, connection: sa.Connection, table: str, target_id: str) -> None:
        self.connection = connection
        self.table = require_table(table)
        self.target_id = target_id

        if _has_unique_key(connection, self.table):
            duplicate_keys = "0"
        else:
            duplicate_keys = _DUPLICATE_KEYS_SQL.format(table=self.table)
        check = _CHECK_SQL.format(
            table=self.table,
            duplicate_keys=duplicate_keys,
            low=COVERED_TIERS.start,
            high=COVERED_TIERS.stop - 1,
        )
        counts = connection.execute(sa.text(check), self._parameters).one()
        check_counts(
            duplicate_keys=counts.duplicate_keys,
            nulls=counts.nulls,
            outside_tiers=counts.outside_tiers,
        )
        if not counts.target_rows:
            raise TargetNotFoundError(target_id)

    @property
    def _parameters(self) -> dict[str, str]:
        return {"target_id": self.target_id}

    def comparison_table(self) -> pl.DataFrame:
        """Table-2."""
        return read_frame(
            self.connection,
            _comparison_query(self.table, _TABLE_2_SQL),
            TABLE_2_SCHEMA,
            self._parameters,
        ).sort(KEY)

    def average_tier_differences(self) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Table-3 for parts A and B, from a single query."""
        averages = pl.read_database(
            sa.text(_TABLE_3_SQL.format(table=self.table, uncovered=UNCOVERED_TIER)),
            self.connection,
            execute_options={"parameters": self._parameters},
            schema_overrides=polars_schema(_AVERAGES_SCHEMA),
        )
        all_tiers, changed_tiers = (
            averages.select("formulary_id", tier_difference=column).cast(
                polars_schema(TABLE_3_SCHEMA)
            )
            for column in ("all_tiers", "changed_tiers")
        )
        return all_tiers, changed_tiers

    def average_tier_difference(self, *, exclude_equal: bool = False) -> pl.DataFrame:
        """Table-3, for part B with `exclude_equal`."""
        all_tiers, changed_tiers = self.average_tier_differences()
        return changed_tiers if exclude_equal else all_tiers
