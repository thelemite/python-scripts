#!/usr/bin/env python3
"""Download files from URLs stored in a database column.

Usage:
    python file_downloader.py \
        --host <db host> \
        --database <db name> \
        --table <table name> \
        --user <db user> \
        --password <db password> \
        --column <column name> \
        --output <local directory> \
        [--delay <seconds>] \
        [--max-files <int>]

The script reads the specified column from the given table, treats each value as a URL,
downloads the content using httpx, and saves it to the output directory. An optional
`--delay` argument can be used to throttle the request frequency.
"""

import argparse
import os
import time
import pathlib
import sys
import logging
from urllib.parse import urlparse, unquote

import pandas as pd
import httpx
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download files from URLs stored in a DB column.")
    parser.add_argument("--host", required=True, help="Source database host")
    parser.add_argument("--database", required=True, help="Source database name")
    parser.add_argument("--table", required=True, help="Source table name")
    parser.add_argument("--user", required=True, help="Database user")
    parser.add_argument("--password", required=True, help="Database password")
    parser.add_argument("--column", required=True, help="Column name containing URLs")
    parser.add_argument("--output", required=True, help="Local directory to save files")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between requests (default: 0)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to download (optional)",
    )
    return parser.parse_args()


def build_engine(host: str, database: str, user: str, password: str):
    # Default to MySQL using pymysql driver; adjust if needed.
    url = f"mysql+pymysql://{user}:{password}@{host}/{database}"
    try:
        engine = create_engine(url)
        # Test connection quickly
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return engine
    except Exception as e:
        logging.error("Failed to create DB engine: %s", e)
        sys.exit(1)


def fetch_urls(engine, table: str, column: str) -> pd.Series:
    query = f"SELECT {column} FROM {table}"
    try:
        df = pd.read_sql_query(query, con=engine)
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found in query result")
        return df[column].dropna()
    except Exception as e:
        logging.error("Error fetching URLs: %s", e)
        sys.exit(1)


def determine_filename(url: str, response: httpx.Response) -> str:
    # Prefer Content-Disposition filename if present
    cd = response.headers.get("content-disposition")
    if cd:
        parts = cd.split(";")
        for part in parts:
            if part.strip().lower().startswith("filename="):
                filename = part.split("=", 1)[1].strip(' "')
                return filename
    # Fallback to URL path basename
    path = urlparse(url).path
    basename = os.path.basename(path)
    if basename:
        return unquote(basename)
    # As a last resort, generate a uuid
    import uuid
    return f"file_{uuid.uuid4().hex}"


def download_file(url: str, dest_dir: pathlib.Path) -> None:
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as resp:
            resp.raise_for_status()
            filename = determine_filename(url, resp)
            dest_path = dest_dir / filename
            # Avoid overwriting existing files
            counter = 1
            while dest_path.exists():
                stem = dest_path.stem
                suffix = dest_path.suffix
                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        logging.info("Downloaded %s -> %s", url, dest_path)
    except Exception as exc:
        logging.error("Failed to download %s: %s", url, exc)


def main():
    args = parse_args()
    output_dir = pathlib.Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = build_engine(args.host, args.database, args.user, args.password)
    urls = fetch_urls(engine, args.table, args.column)
    if args.max_files is not None:
        urls = urls.head(args.max_files)

    for url in urls:
        if not isinstance(url, str) or not url.strip():
            continue
        download_file(url.strip(), output_dir)
        if args.delay > 0:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
