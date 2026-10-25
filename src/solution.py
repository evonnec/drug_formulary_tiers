import argparse
import time
from collections.abc import Sequence

# pandas and sqlalchemy are only imported on first use, so `--help` stays fast.
# Annotations are evaluated lazily (PEP 649), so using them in signatures
# does not trigger the import either.
lazy import pandas as pd
lazy import sqlalchemy as sa

DATABASE_URL = "postgresql+psycopg://appuser:appuser@localhost:5432/formulary"
COLUMNS = ("formulary_id", "tier_level_value", "rxcui")
DROPPED_COLUMNS = ["tier_level_value_target", "tier_level_value"]


def connect_to_db(url: str = DATABASE_URL) -> sa.Engine:
    return sa.create_engine(url)


def load_table_into_dataframe(
    tablename: str, db_conn: sa.Engine, columns: Sequence[str]
) -> pd.DataFrame:
    table = sa.table(tablename, *(sa.column(c) for c in columns))
    with db_conn.connect() as connection:
        return pd.read_sql_query(sql=sa.select(table), con=connection)


def join_self_tables(
    df: pd.DataFrame, col: str, condition: str | None = None
) -> pd.DataFrame:
    new_df = df.merge(right=df, on=col, how="inner", suffixes=("_target", ""))

    if condition:
        new_df = new_df.loc[new_df.formulary_id == condition]
    return new_df


def add_tier_difference(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        tier_difference=df["tier_level_value_target"] - df["tier_level_value"]
    )


def drop_unchanged_tiers(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df.tier_difference != 0]


def average_tier_difference(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("formulary_id").mean(numeric_only=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Average drug tier difference between formularies.",
        suggest_on_error=True,
    )
    parser.add_argument(
        "formulary_id",
        nargs="?",
        help=(
            "target formulary_id to compare against in the full `formulary` "
            "table (Part 3); omit to run Part 1 on `test_formulary`"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    start = time.perf_counter()
    db_conn = connect_to_db()

    tablename = "test_formulary" if args.formulary_id is None else "formulary"

    df_formulary = load_table_into_dataframe(tablename, db_conn, COLUMNS)
    print(f"Table-1: \n{df_formulary}\n")

    if args.formulary_id is None:
        print("Part 1:\n")
    else:
        print(f"Part 3: `formulary_id` = '{args.formulary_id}'\n")
    tableA = join_self_tables(df=df_formulary, col="rxcui", condition=args.formulary_id)

    ## table 2 ##
    print(f"Table-2: \n{tableA}\n")

    ## add tier_difference column ##
    tableA = add_tier_difference(tableA)
    print(f"table A add tier diff col \n{tableA}\n")
    tableB = drop_unchanged_tiers(tableA)
    print(f"table B add tier diff col \n{tableB}\n")

    ## drop cols ##
    tableA = tableA.drop(columns=DROPPED_COLUMNS)
    print(f"table A drop col \n{tableA}\n")
    tableB = tableB.drop(columns=DROPPED_COLUMNS)
    print(f"table B drop col \n{tableB}\n")

    ## take mean ##
    formularyIdTableA = average_tier_difference(tableA)
    formularyIdTableB = average_tier_difference(tableB)
    print(f"Table-3 for A: \n{formularyIdTableA}\n")
    print(f"Table-3 for B: \n{formularyIdTableB}\n")

    print(f"Execution time: {time.perf_counter() - start:.2f}s")


if __name__ == "__main__":
    main()
