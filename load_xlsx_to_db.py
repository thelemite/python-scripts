#!/usr/bin/env python3
"""Load an Excel (.xlsx) file's single sheet into a MySQL database table using pandas and SQLAlchemy.

Usage:
    python load_xlsx_to_db.py \
        --file <excel_path> \
        --host <db_host> \
        --user <db_user> \
        --password <db_password> \
        --dbname <database_name> \
        --table <table_name> \
        --sheet_name <sheet_name>

The script builds a MySQL connection URL (using the PyMySQL driver) from the supplied arguments.
"""

import argparse
import sys
import pandas as pd
from sqlalchemy import create_engine


def parse_args():
    parser = argparse.ArgumentParser(description="Load an Excel file into a DB table.")
    parser.add_argument("--file", required=True, help="Path to the source .xlsx file")
    parser.add_argument("--host", required=True, help="Database host (e.g., localhost or 127.0.0.1)")
    parser.add_argument("--user", required=True, help="Database user name")
    parser.add_argument("--password", required=True, help="Database password")
    parser.add_argument("--dbname", required=True, help="Database name")
    parser.add_argument("--table", required=True, help="Target table name in the database")
    parser.add_argument("--sheet_name", required=False, help="Sheet name in xlsx file, Optional, if ommitted and multiple sheets exist, pandas will load the first sheet by default")
    return parser.parse_args()


def main():
    args = parse_args()
    # Build a MySQL connection URL using the PyMySQL driver.
    conn_url = f"mysql+pymysql://{args.user}:{args.password}@{args.host}/{args.dbname}"
    try:
        engine = create_engine(conn_url)
    except Exception as e:
        sys.stderr.write(f"Failed to create engine: {e}\n")
        sys.exit(1)

    try:
        if args.sheet_name:
            df = pd.read_excel(args.file, sheet_name=args.sheet_name)
        else:
            df = pd.read_excel(args.file)
    except Exception as e:
        sys.stderr.write(f"Failed to read Excel file '{args.file}': {e}\n")
        sys.exit(1)

    try:
        df.to_sql(name=args.table, con=engine, if_exists="replace", index=False)
        print(f"Successfully loaded {len(df)} rows into table '{args.table}'.")
    except Exception as e:
        sys.stderr.write(f"Failed to write to table '{args.table}': {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
