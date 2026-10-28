"""SQL quiz: sign in with Supabase Auth, write a query, run it against live Postgres."""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

import db
import rag
from questions import QUESTIONS

load_dotenv()
st.set_page_config(page_title="SQL Quiz: Course Enrollments", page_icon="🗄️", layout="wide")


_MISSING = object()


def cfg(key, default=_MISSING):
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        if default is _MISSING:
            return os.environ[key]
        return os.environ.get(key, default)


# ------------------------------------------------------------------ auth
def supabase():
    # One client per browser session: it holds that user's auth session.
    if "sb" not in st.session_state:
        st.session_state.sb = create_client(cfg("SUPABASE_URL"), cfg("SUPABASE_ANON_KEY"))
    return st.session_state.sb


def current_user():
    return st.session_state.get("user")


def auth_sidebar():
    st.sidebar.header("Account")
    user = current_user()
    if user:
        st.sidebar.success(f"Signed in as **{user['email']}**")
        if st.sidebar.button("Sign out"):
            try:
                supabase().auth.sign_out()
            finally:
                st.session_state.pop("user", None)
                st.session_state.pop("sb", None)
            st.rerun()
        return

    sign_in, sign_up = st.sidebar.tabs(["Sign in", "Sign up"])
    with sign_in.form("sign_in"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            try:
                res = supabase().auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = {"id": res.user.id, "email": res.user.email}
                st.rerun()
            except Exception as exc:  # supabase raises AuthApiError with a readable message
                st.error(f"Sign-in failed: {exc}")
    with sign_up.form("sign_up"):
        email = st.text_input("Email", key="su_email")
        password = st.text_input("Password (6+ characters)", type="password", key="su_pw")
        if st.form_submit_button("Create account"):
            try:
                res = supabase().auth.sign_up({"email": email, "password": password})
                if res.session:
                    st.session_state.user = {"id": res.user.id, "email": res.user.email}
                    st.rerun()
                st.info("Account created. Check your email to confirm it, then sign in.")
            except Exception as exc:
                st.error(f"Sign-up failed: {exc}")


# -------------------------------------------------------------- database
@st.cache_data(ttl=300)
def load_questions():
    with psycopg.connect(cfg("APP_DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, prompt, points, hint_sql, hint_result FROM app.questions ORDER BY id"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def audit(user, action, question_id, sql_text, row_count=None, success=True, error=None):
    try:
        with psycopg.connect(cfg("APP_DATABASE_URL")) as conn:
            conn.execute(
                """
                INSERT INTO app.audit_log
                    (user_id, user_email, action, question_id, sql_text, row_count, success, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user["id"], user["email"], action, question_id, sql_text, row_count, success, error),
            )
    except psycopg.Error as exc:
        st.warning(f"Could not write audit log: {exc}")


def save_answer(user, question_id, sql_text):
    with psycopg.connect(cfg("APP_DATABASE_URL")) as conn:
        conn.execute(
            "INSERT INTO app.saved_answers (user_id, user_email, question_id, sql_text) "
            "VALUES (%s, %s, %s, %s)",
            (user["id"], user["email"], question_id, sql_text),
        )


def my_answers(user):
    with psycopg.connect(cfg("APP_DATABASE_URL")) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT question_id AS question, sql_text AS saved_sql, saved_at "
            "FROM app.saved_answers WHERE user_id = %s ORDER BY saved_at DESC LIMIT 50",
            (user["id"],),
        )
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def frame(columns, rows):
    # st.dataframe needs unique column names; "SELECT a.x, b.x" would clash.
    seen, names = {}, []
    for c in columns:
        seen[c] = seen.get(c, 0) + 1
        names.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
    return pd.DataFrame(rows, columns=names)


# -------------------------------------------------------------------- UI
SCHEMA_DOC = """
| table | columns |
|---|---|
| `quiz.students` | `student_id` (PK), `full_name`, `program` (MIDS / MEM / MBA), `start_year` |
| `quiz.courses` | `course_id` (PK, e.g. `IDS706`), `title`, `department`, `credits` |
| `quiz.enrollments` | `student_id` (FK), `course_id` (FK), `semester` (`Fall 2026` / `Spring 2026`), `grade` (0–100) |
"""


def question_page(q, user):
    st.subheader(f"Q{q['id']}. {q['title']}  ·  {q['points']} points")
    st.markdown(q["prompt"])

    with st.expander("Hint: expected SQL and expected result"):
        st.code(q["hint_sql"], language="sql")
        st.dataframe(frame(q["hint_result"]["columns"], q["hint_result"]["rows"]), hide_index=True)

    sql_text = st.text_area(
        "Your SQL", key=f"sql_{q['id']}", height=160,
        placeholder="SELECT ... FROM quiz.students ...",
    )
    if not user:
        st.info("Sign in (sidebar) to run queries and save answers.")
    run_col, save_col, _ = st.columns([1, 1, 6])
    run = run_col.button("▶ Run", type="primary", disabled=not user, key=f"run_{q['id']}")
    save = save_col.button("💾 Save answer", disabled=not user, key=f"save_{q['id']}")

    # Buttons are disabled when signed out, but check again server-side.
    if (run or save) and not user:
        st.error("You must be signed in.")
        return

    if run:
        cleaned, err = db.check_sql(sql_text)
        if err:
            st.error(err)
            return
        try:
            columns, rows, truncated = db.run_readonly(cfg("TAKER_DATABASE_URL"), cleaned)
        except psycopg.Error as exc:
            msg = str(exc).strip()
            audit(user, "run", q["id"], cleaned, success=False, error=msg)
            st.error(msg)
            return
        audit(user, "run", q["id"], cleaned, row_count=len(rows))
        st.caption(f"{len(rows)} row(s){' (showing first 200)' if truncated else ''}")
        st.dataframe(frame(columns, rows), hide_index=True)
        if db.results_match(columns, rows, q["hint_result"]):
            st.success("✅ Your result matches the expected result.")
        else:
            st.warning("Result differs from the expected result. Check the columns and filters.")

    if save:
        if not sql_text.strip():
            st.error("Nothing to save yet.")
            return
        save_answer(user, q["id"], sql_text)
        audit(user, "save", q["id"], sql_text)
        st.success("Answer saved.")


# ------------------------------------------------------------ Ask AI (RAG)
DEFAULT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"  # Gemini (OpenAI-compatible)
DEFAULT_LLM_MODEL = "gemini-3.5-flash"
FALLBACK_LLM_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest"]


@st.cache_resource(show_spinner="Building the vector database (first load only)...")
def vector_store():
    # Schema documents come from the live Postgres catalog, read as quiz_taker.
    return rag.build_store(rag.schema_documents(cfg("TAKER_DATABASE_URL")))


@st.cache_resource
def llm_client():
    return OpenAI(
        base_url=cfg("LLM_BASE_URL", DEFAULT_LLM_BASE_URL), api_key=cfg("LLM_API_KEY"),
        timeout=60, max_retries=1,
    )


CUSTOM = "✏️ Ask my own question"


def ask_ai_page(user):
    st.subheader("🤖 Ask AI: natural language → SQL (RAG)")
    st.write(
        "Your question is embedded and matched against a **ChromaDB** vector database of "
        "schema descriptions, business rules and example queries. The retrieved context "
        "is sent to **Google Gemini**, which writes the SQL. The SQL then "
        "runs read-only against the live database and is checked against the quiz answer."
    )
    options = [f"Q{q['id']}. {q['nl_question']}" for q in QUESTIONS] + [CUSTOM]
    picked = st.selectbox("Pick a quiz question or ask your own", options)
    quiz_q = None if picked == CUSTOM else QUESTIONS[options.index(picked)]
    question = st.text_area(
        "Question", value="" if quiz_q is None else quiz_q["nl_question"], height=90,
        key=f"nlq_{picked}", placeholder="e.g. Which MIDS students got above 90 in IDS706?",
    )
    if not user:
        st.info("Sign in (sidebar) to generate SQL.")
    if not st.button("✨ Generate SQL", type="primary", disabled=not user):
        return
    if not question.strip():
        st.error("Enter a question first.")
        return

    with st.spinner("Retrieving context..."):
        hits = rag.retrieve(vector_store(), question)
    with st.expander(f"1 · Retrieved context ({len(hits)} documents from ChromaDB)", expanded=True):
        st.dataframe(
            pd.DataFrame(
                [{"type": h["type"], "id": h["id"], "distance": round(h["distance"], 3),
                  "text": h["text"]} for h in hits]
            ),
            hide_index=True,
        )

    models = [cfg("LLM_MODEL", DEFAULT_LLM_MODEL)] + FALLBACK_LLM_MODELS
    try:
        with st.spinner(f"Asking {models[0]}..."):
            sql_text, model = rag.generate_sql(llm_client(), models, question, hits)
    except Exception as exc:
        st.error(f"AI API call failed: {exc}")
        return
    st.markdown(f"**2 · Generated SQL** (model: `{model}`)")
    st.code(sql_text, language="sql")

    st.markdown("**3 · Executed read-only against Supabase**")
    cleaned, err = db.check_sql(sql_text)
    if err:
        audit(user, "ai", quiz_q and quiz_q["id"], sql_text, success=False, error=err)
        st.error(f"Not executed: {err}")
        return
    try:
        columns, rows, truncated = db.run_readonly(cfg("TAKER_DATABASE_URL"), cleaned)
    except psycopg.Error as exc:
        msg = str(exc).strip()
        audit(user, "ai", quiz_q and quiz_q["id"], cleaned, success=False, error=msg)
        st.error(msg)
        return
    audit(user, "ai", quiz_q and quiz_q["id"], cleaned, row_count=len(rows))
    st.caption(f"{len(rows)} row(s){' (showing first 200)' if truncated else ''}")
    st.dataframe(frame(columns, rows), hide_index=True)

    st.markdown("**4 · Validation**")
    if quiz_q is None:
        st.info("Custom question: there is no expected answer to compare against.")
    elif db.results_match(columns, rows, quiz_q["hint_result"]):
        st.success(f"✅ Correct: the result matches the expected answer for Q{quiz_q['id']}.")
    else:
        st.error(f"❌ Incorrect: the result differs from the expected answer for Q{quiz_q['id']}.")
        st.dataframe(
            frame(quiz_q["hint_result"]["columns"], quiz_q["hint_result"]["rows"]),
            hide_index=True,
        )


def main():
    auth_sidebar()
    user = current_user()

    st.title("🗄️ SQL Quiz: Graduate Course Enrollments")
    st.write(
        "Five questions, 20 points. Every answer is a SQL query that runs against a live "
        "PostgreSQL database hosted on Supabase. Queries run as a read-only role."
    )
    with st.expander("Database schema", expanded=False):
        st.markdown(SCHEMA_DOC)

    mode = st.sidebar.radio("Mode", ["📝 Take the quiz", "🤖 Ask AI (RAG)"])
    if mode.startswith("🤖"):
        ask_ai_page(user)
        return

    questions = load_questions()
    labels = [f"Q{q['id']}. {q['title']} ({q['points']} pts)" for q in questions]
    choice = st.sidebar.radio("Question", range(len(questions)), format_func=labels.__getitem__)
    st.sidebar.caption(f"Total: {sum(q['points'] for q in questions)} points")

    question_page(questions[choice], user)

    if user:
        with st.expander("My saved answers"):
            st.dataframe(my_answers(user), hide_index=True)


main()
