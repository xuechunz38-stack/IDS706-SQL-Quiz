"""Database helpers shared by the app and the scripts.

Every query the app itself issues uses bound parameters (never f-strings).
The only free-form SQL is what a quiz taker types, and that runs as the
read-only quiz_taker role inside a read-only transaction.
"""

import re
from decimal import Decimal

import psycopg

MAX_ROWS = 200
ALLOWED_START = ("select", "with", "values", "table", "explain")


def check_sql(sql_text):
    """Return (cleaned_sql, error). Allows a single read-only statement."""
    cleaned = sql_text.strip().rstrip(";").strip()
    if not cleaned:
        return None, "Enter a SQL query first."
    # Strip leading comments before checking the first keyword.
    body = re.sub(r"^(\s*(--[^\n]*\n|/\*.*?\*/))*\s*", "", cleaned + "\n", flags=re.S)
    if not body.lower().startswith(ALLOWED_START):
        return None, "Only SELECT / WITH queries are allowed in this quiz."
    if ";" in re.sub(r"'(?:[^']|'')*'", "", cleaned):
        return None, "Run one statement at a time (remove the extra ';')."
    return cleaned, None


def run_readonly(taker_url, sql_text, max_rows=MAX_ROWS):
    """Run a quiz taker's query. Returns (columns, rows, truncated)."""
    with psycopg.connect(taker_url, connect_timeout=10) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(sql_text)
            if cur.description is None:
                return [], [], False
            columns = [d.name for d in cur.description]
            rows = cur.fetchmany(max_rows + 1)
        conn.rollback()
    return columns, [list(r) for r in rows[:max_rows]], len(rows) > max_rows


def _norm(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 4)
    return str(value)


def results_match(columns, rows, expected):
    """Compare a result set to a hint. Column count and the multiset of rows
    must match; column names and row order are not graded."""
    if len(columns) != len(expected["columns"]):
        return False
    got = sorted((tuple(_norm(v) for v in r) for r in rows), key=repr)
    want = sorted((tuple(_norm(v) for v in r) for r in expected["rows"]), key=repr)
    return got == want


def to_jsonable(rows):
    return [[_norm(v) for v in r] for r in rows]
