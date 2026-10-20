"""Health check run by GitHub Actions against the hosted database.

Connects with the DATABASE_URL secret and fails (exit 1) unless:
  * the dataset and all quiz questions are loaded,
  * every question's hint_sql still returns its stored hint_result,
  * quiz_taker / quiz_app have only the privileges they should,
  * the audit log hash chain is intact (no edited or deleted rows).
"""

import os
import pathlib
import sys

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import db  # noqa: E402

load_dotenv(ROOT / ".env")

# (role, object, privilege, expected)
PRIVILEGES = [
    ("quiz_taker", "quiz.enrollments", "SELECT", True),
    ("quiz_taker", "quiz.enrollments", "INSERT", False),
    ("quiz_taker", "app.audit_log", "SELECT", False),
    ("quiz_taker", "app.questions", "SELECT", False),
    ("quiz_app", "app.audit_log", "INSERT", True),
    ("quiz_app", "app.audit_log", "UPDATE", False),
    ("quiz_app", "app.audit_log", "DELETE", False),
    ("quiz_app", "app.audit_log", "TRUNCATE", False),
]

def main():
    failures = []
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
        cur = conn.cursor()
        cur.execute("SELECT current_user, version()")
        user, version = cur.fetchone()
        print(f"Connected as {user}: {version.split(',')[0]}")

        for table in ("students", "courses", "enrollments"):
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("quiz", table)))
            n = cur.fetchone()[0]
            print(f"  quiz.{table}: {n} rows")
            if n == 0:
                failures.append(f"quiz.{table} is empty")

        cur.execute("SELECT id, points, hint_sql, hint_result FROM app.questions ORDER BY id")
        questions = cur.fetchall()
        total = sum(q[1] for q in questions)
        print(f"  {len(questions)} questions, {total} points")
        if total != 20:
            failures.append(f"quiz is worth {total} points, expected 20")
        for qid, _, hint_sql, hint_result in questions:
            columns, rows, _ = db.run_readonly(os.environ["DATABASE_URL"], hint_sql.rstrip().rstrip(";"))
            ok = db.results_match(columns, rows, hint_result)
            print(f"  Q{qid} hint matches stored result: {ok}")
            if not ok:
                failures.append(f"Q{qid} hint_sql no longer returns hint_result")

        for role, obj, priv, expected in PRIVILEGES:
            cur.execute("SELECT has_table_privilege(%s, %s, %s)", (role, obj, priv))
            actual = cur.fetchone()[0]
            if actual != expected:
                failures.append(f"{role} {priv} on {obj} is {actual}, expected {expected}")
        print(f"  role privileges checked: {len(PRIVILEGES)}")

        # Window functions can't sit inside FILTER directly; wrap in a subquery.
        cur.execute(
            "SELECT count(*) FILTER (WHERE bad), count(*) FROM ("
            " SELECT row_hash <> app.audit_row_hash(prev_hash, user_id, user_email, action,"
            "   question_id, sql_text, row_count, success, error, created_at)"
            " OR prev_hash <> coalesce(lag(row_hash) OVER (ORDER BY id), 'GENESIS') AS bad"
            " FROM app.audit_log) t"
        )
        broken, rows = cur.fetchone()
        print(f"  audit log: {rows} rows, {broken} broken links")
        if broken:
            failures.append(f"audit log hash chain broken at {broken} row(s)")

    if failures:
        print("\nFAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("\nAll checks passed.")

if __name__ == "__main__":
    main()
