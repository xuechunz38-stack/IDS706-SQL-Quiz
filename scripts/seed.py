"""Create the schema, load the dataset and questions, and set up the roles.

Usage:  python scripts/seed.py
Reads DATABASE_URL (owner, e.g. the Supabase "postgres" user), TAKER_PASSWORD
and APP_PASSWORD from the environment or a local .env file.
"""

import json
import os
import pathlib
import sys

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from questions import QUESTIONS  # noqa: E402

load_dotenv(ROOT / ".env")


def ensure_role(cur, name, password):
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    verb = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(
        sql.SQL("{} ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
            sql.SQL(verb), sql.Identifier(name), sql.Literal(password)
        )
    )


def main():
    url = os.environ["DATABASE_URL"]
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute((ROOT / "sql/schema.sql").read_text())
        cur.execute((ROOT / "sql/seed.sql").read_text())
        for q in QUESTIONS:
            cur.execute(
                """
                INSERT INTO app.questions (id, title, prompt, points, hint_sql, hint_result)
                VALUES (%(id)s, %(title)s, %(prompt)s, %(points)s, %(hint_sql)s, %(hint_result)s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title, prompt = EXCLUDED.prompt,
                    points = EXCLUDED.points, hint_sql = EXCLUDED.hint_sql,
                    hint_result = EXCLUDED.hint_result
                """,
                {**q, "hint_result": json.dumps(q["hint_result"])},
            )
        cur.execute(
            "DELETE FROM app.questions WHERE id <> ALL(%s)",
            ([q["id"] for q in QUESTIONS],),
        )
        ensure_role(cur, "quiz_taker", os.environ["TAKER_PASSWORD"])
        ensure_role(cur, "quiz_app", os.environ["APP_PASSWORD"])
        cur.execute((ROOT / "sql/grants.sql").read_text())
    print(f"Seeded {len(QUESTIONS)} questions and the quiz dataset.")


if __name__ == "__main__":
    main()
