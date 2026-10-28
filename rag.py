"""RAG pipeline for Text-to-SQL.

    question ──► ChromaDB similarity search ──► prompt with retrieved context ──► LLM ──► SQL

The vector store holds three kinds of documents:
  * schema    one per table, generated from the live Postgres catalog (columns,
              types, keys, and the distinct values of small text columns)
  * rule      business semantics from knowledge.BUSINESS_RULES
  * example   few-shot question/SQL pairs from knowledge.FEW_SHOT_EXAMPLES
"""

import re

import chromadb
import psycopg
from openai import InternalServerError, NotFoundError, OpenAI, RateLimitError

from knowledge import BUSINESS_RULES, FEW_SHOT_EXAMPLES

COLLECTION = "text2sql_knowledge"
TOP_K = {"schema": 3, "rule": 4, "example": 3}

COLUMNS_SQL = """
SELECT c.relname AS table_name, a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type, a.attnotnull AS not_null
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""

# pg_constraint is readable by every role, unlike information_schema's
# constraint views, which only show tables the current role owns.
KEYS_SQL = """
SELECT c.relname AS table_name, pg_get_constraintdef(k.oid) AS definition
FROM pg_constraint k
JOIN pg_class c ON c.oid = k.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND k.contype IN ('p', 'f')
ORDER BY c.relname, k.contype DESC
"""

# Low-cardinality text columns whose values help the model write filters.
VALUE_COLUMNS = {
    "students": ["program"],
    "courses": ["department"],
    "enrollments": ["semester"],
}


def schema_documents(database_url, schema="quiz"):
    """Describe each table in `schema` from the Postgres catalog."""
    tables = {}
    with psycopg.connect(database_url, connect_timeout=10) as conn, conn.cursor() as cur:
        cur.execute(COLUMNS_SQL, (schema,))
        for table, column, dtype, not_null in cur.fetchall():
            tables.setdefault(table, {"columns": [], "keys": [], "values": {}})
            tables[table]["columns"].append(
                f"{column} {dtype}{' NOT NULL' if not_null else ''}"
            )
        cur.execute(KEYS_SQL, (schema,))
        for table, definition in cur.fetchall():
            tables[table]["keys"].append(definition)
        for table, columns in VALUE_COLUMNS.items():
            if table not in tables:
                continue
            for column in columns:
                cur.execute(
                    psycopg.sql.SQL("SELECT DISTINCT {} FROM {} ORDER BY 1").format(
                        psycopg.sql.Identifier(column), psycopg.sql.Identifier(schema, table)
                    )
                )
                tables[table]["values"][column] = [r[0] for r in cur.fetchall()]

    docs = []
    for table, info in tables.items():
        lines = [f"Table {schema}.{table}", "Columns: " + ", ".join(info["columns"])]
        lines += [f"Key: {k}" for k in info["keys"]]
        for column, values in info["values"].items():
            lines.append(f"Values of {column}: " + ", ".join(repr(v) for v in values))
        docs.append((f"schema_{table}", "\n".join(lines)))
    return docs


def build_store(schema_docs):
    """Create an in-memory Chroma collection with all knowledge documents.

    Chroma embeds the text with its default local model (all-MiniLM-L6-v2 via
    ONNX), so no embedding API key is needed.
    """
    client = chromadb.EphemeralClient()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    ids, texts, metas = [], [], []
    for doc_id, text in schema_docs:
        ids.append(doc_id), texts.append(text), metas.append({"type": "schema"})
    for doc_id, text in BUSINESS_RULES:
        ids.append(doc_id), texts.append(text), metas.append({"type": "rule"})
    for i, (question, sql_text) in enumerate(FEW_SHOT_EXAMPLES, 1):
        ids.append(f"example_{i}")
        texts.append(f"Question: {question}\nSQL:\n{sql_text}")
        metas.append({"type": "example"})
    collection.add(ids=ids, documents=texts, metadatas=metas)
    return collection


def retrieve(collection, question, top_k=TOP_K):
    """Return the most similar documents of each type, closest first."""
    hits = []
    for doc_type, k in top_k.items():
        res = collection.query(query_texts=[question], n_results=k, where={"type": doc_type})
        for doc_id, text, dist in zip(res["ids"][0], res["documents"][0], res["distances"][0]):
            hits.append({"id": doc_id, "type": doc_type, "distance": dist, "text": text})
    return hits


SYSTEM_PROMPT = (
    "You translate questions about a university course-enrollment database into "
    "PostgreSQL. Use only the tables, columns and values in the provided context. "
    "Reply with a single SELECT statement inside a ```sql code block and nothing else."
)


def build_messages(question, hits):
    sections = {"schema": [], "rule": [], "example": []}
    for h in hits:
        sections[h["type"]].append(h["text"])
    context = (
        "### Relevant schema\n" + "\n\n".join(sections["schema"])
        + "\n\n### Business rules\n" + "\n".join(f"- {t}" for t in sections["rule"])
        + "\n\n### Similar examples\n" + "\n\n".join(sections["example"])
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\n### Question\n{question}"},
    ]


def extract_sql(text):
    """Pull the SQL out of a model reply (fenced or bare) and keep one statement."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.S | re.I)
    sql_text = (match.group(1) if match else text).strip()
    sql_text = sql_text.rstrip().rstrip(";").strip()
    return sql_text + ";" if sql_text else ""


def generate_sql(client: OpenAI, models, question, hits):
    """Ask the first model that is available. Returns (sql, model_used).

    Free-tier Gemini models sometimes answer 503 "high demand" or 429, so the
    caller passes a primary model followed by fallbacks.
    """
    models = [models] if isinstance(models, str) else list(models)
    messages = build_messages(question, hits)
    for i, model in enumerate(models):
        try:
            response = client.chat.completions.create(model=model, messages=messages)
        except (InternalServerError, RateLimitError, NotFoundError):
            if i == len(models) - 1:
                raise
            continue
        return extract_sql(response.choices[0].message.content or ""), model
