"""End-to-end RAG check, run by GitHub Actions and locally.

1. Builds the ChromaDB knowledge base from the live database schema.
2. Retrieves context for each quiz question (fails if retrieval returns nothing).
3. If LLM_API_KEY is set, generates SQL for each question, runs it read-only and
   reports how many results match the expected answers. Wrong SQL does not fail
   the job: the assignment grades the pipeline, not SQL accuracy.
"""

import os
import pathlib
import sys

from dotenv import load_dotenv
from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import db  # noqa: E402
import rag  # noqa: E402
from questions import QUESTIONS  # noqa: E402

load_dotenv(ROOT / ".env")


def main():
    url = os.environ["DATABASE_URL"]
    docs = rag.schema_documents(url)
    store = rag.build_store(docs)
    print(f"Vector store: {store.count()} documents ({len(docs)} schema docs from Postgres)")

    api_key = os.environ.get("LLM_API_KEY")
    client = model = None
    if api_key:
        client = OpenAI(base_url=os.environ.get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
                        api_key=api_key, timeout=60, max_retries=1)
        model = [os.environ.get("LLM_MODEL", "gemini-3.5-flash"), "gemini-3.1-flash-lite"]
        print(f"LLM: {model[0]} (fallback {model[1]})")
    else:
        print("LLM_API_KEY not set: checking retrieval only")

    correct = 0
    for q in QUESTIONS:
        hits = rag.retrieve(store, q["nl_question"])
        print(f"\nQ{q['id']}: {q['nl_question']}")
        print("  retrieved: " + ", ".join(f"{h['id']}({h['distance']:.2f})" for h in hits))
        if not hits or not any(h["type"] == "schema" for h in hits):
            sys.exit(f"Retrieval returned no schema context for Q{q['id']}")
        if not client:
            continue
        sql_text, used = rag.generate_sql(client, model, q["nl_question"], hits)
        print(f"  SQL ({used}): " + " ".join(sql_text.split()))
        cleaned, err = db.check_sql(sql_text)
        if err:
            print(f"  not executed: {err}")
            continue
        try:
            columns, rows, _ = db.run_readonly(url, cleaned)
        except Exception as exc:  # report and keep going
            print(f"  execution error: {str(exc).splitlines()[0]}")
            continue
        ok = db.results_match(columns, rows, q["hint_result"])
        correct += ok
        print(f"  {len(rows)} rows -> {'CORRECT' if ok else 'INCORRECT'}")

    if client:
        print(f"\nAccuracy: {correct}/{len(QUESTIONS)} quiz questions answered correctly")
    print("RAG check finished.")


if __name__ == "__main__":
    main()
