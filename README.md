# IDS706 SQL Quiz: Graduate Course Enrollments

[![CI](https://github.com/xuechunz38-stack/IDS706-SQL-Quiz/actions/workflows/ci.yml/badge.svg)](https://github.com/xuechunz38-stack/IDS706-SQL-Quiz/actions/workflows/ci.yml)

**Quiz site: https://ids706-sql-quiz12.streamlit.app/**

A small TA-style SQL quiz. You sign in, pick a question, type a SQL query, press **Run**, and see the rows it returns from a live PostgreSQL database hosted on Supabase. The quiz has five questions worth 20 points in total. Each question includes a hint with the expected SQL and the expected result.

## How to take the quiz

1. Open the quiz site above.
2. In the sidebar, open **Sign up**, enter any email and a password (6+ characters), and click **Create account**. Returning users use **Sign in**.
3. Choose a question in the sidebar (Q1 to Q5).
4. Type your SQL in **Your SQL** and click **▶ Run**. The result table appears below the editor. A green banner means your result set matches the expected result.
5. Click **💾 Save answer** to store your query. Your saved answers are listed under **My saved answers**.
6. Open **Hint: expected SQL and expected result** to see the reference query and its output.

While signed out you can read the questions, but **Run** and **Save answer** are disabled. The server checks again that you are signed in before it runs or saves anything.

Grading compares result sets, not SQL text. Column names and row order are ignored; the number of columns and the rows must match.

## The dataset (topic: course enrollments)

| table | columns |
|---|---|
| `quiz.students` (10 rows) | `student_id` (PK), `full_name`, `program` (MIDS / MEM / MBA), `start_year` |
| `quiz.courses` (7 rows) | `course_id` (PK, e.g. `IDS706`), `title`, `department`, `credits` |
| `quiz.enrollments` (27 rows) | `student_id` (FK), `course_id` (FK), `semester` (`Fall 2026` / `Spring 2026`), `grade` (0–100) |

## The questions (20 points)

| # | Topic | Points | Expected result |
|---|---|---|---|
| Q1 | `WHERE` + `ORDER BY`: MIDS students who started in 2025 | 4 | 3 rows: Ava Chen, Ben Okafor, Isla Novak |
| Q2 | `JOIN` + `GROUP BY`: distinct students per course | 4 | 6 rows, IDS706 first with 6 students |
| Q3 | Aggregation: average grade by department, rounded to 1 decimal | 4 | IDS 87.4, FUQ 87.0, ENG 84.9 |
| Q4 | `HAVING`: students taking 3+ courses in Fall 2026 | 4 | Grace Kim 4, Ava Chen 3, Carla Diaz 3, Dev Patel 3 |
| Q5 | What does this `LEFT JOIN ... IS NULL` query return? | 4 | 1 row: STA601 Bayesian Statistics |

The full prompts, hint SQL, and expected results are in [`questions.py`](questions.py). `scripts/seed.py` loads them into `app.questions`.

## Architecture

```
Browser ──► Streamlit app (Streamlit Community Cloud)
              │  sign up / sign in ──► Supabase Auth
              │  quiz taker's SQL  ──► Postgres as quiz_taker (read-only)
              │  questions, saves, audit ──► Postgres as quiz_app (parameterized)
              ▼
         Supabase PostgreSQL (Session pooler, sslmode=require)
              ▲
GitHub Actions ── DATABASE_URL secret ──► scripts/check_db.py (health check)
```

| Requirement | How it is met |
|---|---|
| Hosted PostgreSQL | Supabase project. Schema in [`sql/schema.sql`](sql/schema.sql), data in [`sql/seed.sql`](sql/seed.sql). The app connects through the **Session pooler** with `sslmode=require`. |
| Authentication | Supabase Auth (email + password) in [`app.py`](app.py). Run and Save are disabled when signed out and checked again on the server. |
| GitHub Actions + Secrets | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the unit tests, then `scripts/check_db.py` against the hosted database using `secrets.DATABASE_URL`. No password is in the repository. It runs on every push, on demand, and daily. |
| SQL quiz (20 pts) | 5 × 4-point SQL questions with hints. A signed-in user runs SQL and sees the live result table. |

### Database roles

| Role | Used by | Can do |
|---|---|---|
| `postgres` (owner) | `seed.py`, `check_db.py`, GitHub Actions | Everything (except edit the audit log, see below) |
| `quiz_taker` | SQL typed by quiz takers | `SELECT` on `quiz.*` only. The role is read-only by default, and every query also runs in a read-only transaction with a 5 s timeout. It has no access to `app.*`. |
| `quiz_app` | The app's own queries | `SELECT` questions, `INSERT`/`SELECT` saved answers and audit rows. No `UPDATE`, `DELETE` or `TRUNCATE`. |

The `quiz` and `app` schemas are not exposed through Supabase's REST API, and the `app` tables have row-level security enabled.

## Extra credit

* **Parameterized queries.** Every query the app issues uses bound parameters (`%s`) through psycopg. There is no f-string SQL. Role passwords in `seed.py` are set with `psycopg.sql.Literal`. The only free-form SQL is what the quiz taker types, and it runs as the read-only `quiz_taker` role. `db.check_sql` also allows only a single `SELECT`/`WITH` statement.
* **Audit log.** Every Run (successful or failed) and every Save is written to `app.audit_log`. Each row records the user id and email, the action, the question, the SQL, the row count, success, the error, and a timestamp.
* **Integrity check.**
  * `quiz_taker` has no privileges on schema `app`, so it cannot read or change the log. `quiz_app` can only insert.
  * Triggers block `UPDATE`, `DELETE` and `TRUNCATE` on `app.audit_log` for every role, including the owner.
  * Each row stores a SHA-256 hash of the previous row (`prev_hash` → `row_hash`), forming a hash chain. `scripts/check_db.py` recomputes the chain in CI and fails if any row was edited or removed, even if someone disabled the triggers first. It also checks with `has_table_privilege` that the roles have exactly the intended privileges.

## Repository layout

```
app.py                  Streamlit UI: auth, question pages, run/save
db.py                   SQL guard, read-only runner, result comparison
questions.py            The 5 questions with hint SQL and expected results
sql/schema.sql          Schemas, tables, RLS, audit triggers + hash chain
sql/seed.sql            Dataset
sql/grants.sql          Privileges and RLS policies for quiz_taker / quiz_app
scripts/seed.py         Applies the SQL, loads questions, creates roles
scripts/check_db.py     CI health check against the hosted database
tests/test_db.py        Unit tests (no database needed)
.github/workflows/ci.yml
```

## Set it up yourself

1. **Create a Supabase project** (free tier). Under **Authentication → Sign In / Providers → Email**, turn off **Confirm email** so new users can sign in immediately.
2. **Get the connection details.** Under **Connect → Session pooler**, copy the URI. Under **Project Settings → API**, copy the project URL and the `anon` public key.
3. **Configure locally.**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   make install
   cp .env.example .env        # fill in the values; .env is git-ignored
   ```
   In `.env`, `DATABASE_URL` is the Session pooler URI for `postgres`. Choose `TAKER_PASSWORD` and `APP_PASSWORD`. `APP_DATABASE_URL` and `TAKER_DATABASE_URL` are the same pooler URI with the user replaced by `quiz_app.<project-ref>` / `quiz_taker.<project-ref>` and the matching password.
4. **Load the database:** `make seed`, then `make check`.
5. **Run locally:** `make run` and open http://localhost:8501.
6. **GitHub Actions:** in the repository go to **Settings → Secrets and variables → Actions** and add a secret named `DATABASE_URL` (the owner pooler URI). Push, or run the **CI** workflow manually.
7. **Deploy:** on [share.streamlit.io](https://share.streamlit.io), create an app from this repository with `app.py` as the entry point and Python 3.12. Under **Advanced settings → Secrets**, paste:
   ```toml
   SUPABASE_URL = "https://<project-ref>.supabase.co"
   SUPABASE_ANON_KEY = "<anon key>"
   APP_DATABASE_URL = "postgresql://quiz_app.<project-ref>:<APP_PASSWORD>@<pooler-host>:5432/postgres?sslmode=require"
   TAKER_DATABASE_URL = "postgresql://quiz_taker.<project-ref>:<TAKER_PASSWORD>@<pooler-host>:5432/postgres?sslmode=require"
   ```
   The app never receives the owner password.

## Tests

```bash
make test     # unit tests: SQL guard, result comparison, quiz totals 20 points
make check    # live checks against the database in DATABASE_URL
```
