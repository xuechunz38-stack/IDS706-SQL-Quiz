import pytest

import rag
from knowledge import BUSINESS_RULES, FEW_SHOT_EXAMPLES
from questions import QUESTIONS

SCHEMA_DOCS = [
    ("schema_students", "Table quiz.students\nColumns: student_id integer, full_name text, "
                        "program text, start_year integer"),
    ("schema_courses", "Table quiz.courses\nColumns: course_id text, title text, "
                       "department text, credits integer"),
    ("schema_enrollments", "Table quiz.enrollments\nColumns: student_id integer, "
                           "course_id text, semester text, grade numeric(4,1)"),
]


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("```sql\nSELECT 1;\n```", "SELECT 1;"),
        ("Here you go:\n```SQL\nSELECT a FROM t\n```\nThanks", "SELECT a FROM t;"),
        ("SELECT 2", "SELECT 2;"),
        ("```\nSELECT 3;;\n```", "SELECT 3;"),
        ("", ""),
    ],
)
def test_extract_sql(reply, expected):
    assert rag.extract_sql(reply) == expected


def test_build_messages_puts_retrieved_context_in_prompt():
    hits = [
        {"type": "schema", "text": "Table quiz.students"},
        {"type": "rule", "text": "Use COUNT(DISTINCT ...)"},
        {"type": "example", "text": "Question: q\nSQL:\nSELECT 1;"},
    ]
    system, user = rag.build_messages("How many students?", hits)
    assert system["role"] == "system" and "SELECT" in system["content"]
    for h in hits:
        assert h["text"] in user["content"]
    assert user["content"].rstrip().endswith("How many students?")


def test_few_shot_examples_are_not_the_quiz_answers():
    quiz_sql = {q["hint_sql"].strip() for q in QUESTIONS}
    assert not quiz_sql & {sql.strip() for _, sql in FEW_SHOT_EXAMPLES}


@pytest.fixture(scope="module")
def store():
    return rag.build_store(SCHEMA_DOCS)


def test_store_holds_every_document(store):
    assert store.count() == len(SCHEMA_DOCS) + len(BUSINESS_RULES) + len(FEW_SHOT_EXAMPLES)


def test_retrieve_returns_top_k_of_each_type(store):
    hits = rag.retrieve(store, "average grade by department")
    types = [h["type"] for h in hits]
    for doc_type, k in rag.TOP_K.items():
        assert types.count(doc_type) == k
    dists = [h["distance"] for h in hits if h["type"] == "rule"]
    assert dists == sorted(dists)


@pytest.mark.parametrize(
    "question, expected_id",
    [
        ("Which courses have no enrollments at all?", "rule_no_enrollments"),
        ("students taking at least 3 courses", "rule_having"),
        ("count distinct students per course", "rule_counting_students"),
    ],
)
def test_retrieval_is_relevant(store, question, expected_id):
    ids = [h["id"] for h in rag.retrieve(store, question) if h["type"] == "rule"]
    assert expected_id in ids
