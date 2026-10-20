import pytest

import db
from questions import QUESTIONS


@pytest.mark.parametrize(
    "sql_text",
    [
        "SELECT * FROM quiz.students",
        "select 1;",
        "WITH t AS (SELECT 1) SELECT * FROM t",
        "-- comment first\nSELECT 1",
        "SELECT 'a;b' AS x",
    ],
)
def test_check_sql_accepts_single_select(sql_text):
    cleaned, err = db.check_sql(sql_text)
    assert err is None
    assert not cleaned.endswith(";")


@pytest.mark.parametrize(
    "sql_text",
    [
        "",
        "   ",
        "DELETE FROM quiz.students",
        "DROP TABLE quiz.students",
        "SELECT 1; DELETE FROM quiz.students",
        "/* sneaky */ UPDATE quiz.courses SET credits = 0",
    ],
)
def test_check_sql_rejects(sql_text):
    cleaned, err = db.check_sql(sql_text)
    assert cleaned is None and err


def test_results_match_ignores_row_order_and_numeric_type():
    expected = {"columns": ["name", "n"], "rows": [["a", 1], ["b", 2]]}
    assert db.results_match(["x", "y"], [["b", 2.0], ["a", 1]], expected)


def test_results_match_detects_differences():
    expected = {"columns": ["name", "n"], "rows": [["a", 1], ["b", 2]]}
    assert not db.results_match(["name"], [["a"], ["b"]], expected)
    assert not db.results_match(["name", "n"], [["a", 1]], expected)
    assert not db.results_match(["name", "n"], [["a", 1], ["b", 3]], expected)


def test_quiz_is_worth_20_points_and_every_question_has_a_hint():
    assert sum(q["points"] for q in QUESTIONS) == 20
    for q in QUESTIONS:
        assert q["hint_sql"].strip()
        assert q["hint_result"]["columns"] and q["hint_result"]["rows"]
