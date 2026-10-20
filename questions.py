"""The quiz: five SQL questions, 4 points each (20 total).

hint_result is the expected output of hint_sql. scripts/check_db.py re-runs
every hint_sql in CI and fails if the database disagrees with it.
"""

QUESTIONS = [
    {
        "id": 1,
        "title": "Filter and sort",
        "points": 4,
        "prompt": (
            "List the `full_name` of every **MIDS** student who started in **2025**, "
            "in alphabetical order."
        ),
        "hint_sql": (
            "SELECT full_name\n"
            "FROM quiz.students\n"
            "WHERE program = 'MIDS' AND start_year = 2025\n"
            "ORDER BY full_name;"
        ),
        "hint_result": {
            "columns": ["full_name"],
            "rows": [["Ava Chen"], ["Ben Okafor"], ["Isla Novak"]],
        },
    },
    {
        "id": 2,
        "title": "GROUP BY with a join",
        "points": 4,
        "prompt": (
            "For each course that has at least one enrollment, return `course_id`, "
            "`title` and the number of distinct students as `n_students`. "
            "Sort by `n_students` descending, then `course_id`."
        ),
        "hint_sql": (
            "SELECT c.course_id, c.title, COUNT(DISTINCT e.student_id) AS n_students\n"
            "FROM quiz.courses c\n"
            "JOIN quiz.enrollments e ON e.course_id = c.course_id\n"
            "GROUP BY c.course_id, c.title\n"
            "ORDER BY n_students DESC, c.course_id;"
        ),
        "hint_result": {
            "columns": ["course_id", "title", "n_students"],
            "rows": [
                ["IDS706", "Data Engineering Systems", 6],
                ["IDS705", "Machine Learning Practice", 5],
                ["ENG540", "Product Design", 4],
                ["IDS702", "Modeling and Representation of Data", 4],
                ["MBA510", "Managerial Economics", 4],
                ["MENG570", "Business Fundamentals for Engineers", 4],
            ],
        },
    },
    {
        "id": 3,
        "title": "Aggregate by department",
        "points": 4,
        "prompt": (
            "Return each `department` and its average grade across all enrollments, "
            "rounded to 1 decimal place, as `avg_grade`. Sort by `avg_grade` descending."
        ),
        "hint_sql": (
            "SELECT c.department, ROUND(AVG(e.grade), 1) AS avg_grade\n"
            "FROM quiz.enrollments e\n"
            "JOIN quiz.courses c ON c.course_id = e.course_id\n"
            "GROUP BY c.department\n"
            "ORDER BY avg_grade DESC;"
        ),
        "hint_result": {
            "columns": ["department", "avg_grade"],
            "rows": [["IDS", 87.4], ["FUQ", 87.0], ["ENG", 84.9]],
        },
    },
    {
        "id": 4,
        "title": "HAVING",
        "points": 4,
        "prompt": (
            "Which students are taking **3 or more** courses in **Fall 2026**? "
            "Return `full_name` and `n_courses`, sorted by `n_courses` descending, "
            "then `full_name`."
        ),
        "hint_sql": (
            "SELECT s.full_name, COUNT(*) AS n_courses\n"
            "FROM quiz.students s\n"
            "JOIN quiz.enrollments e ON e.student_id = s.student_id\n"
            "WHERE e.semester = 'Fall 2026'\n"
            "GROUP BY s.full_name\n"
            "HAVING COUNT(*) >= 3\n"
            "ORDER BY n_courses DESC, s.full_name;"
        ),
        "hint_result": {
            "columns": ["full_name", "n_courses"],
            "rows": [
                ["Grace Kim", 4],
                ["Ava Chen", 3],
                ["Carla Diaz", 3],
                ["Dev Patel", 3],
            ],
        },
    },
    {
        "id": 5,
        "title": "What does this query return?",
        "points": 4,
        "prompt": (
            "State what the following query returns, then run it to check:\n\n"
            "```sql\n"
            "SELECT c.course_id, c.title\n"
            "FROM quiz.courses c\n"
            "LEFT JOIN quiz.enrollments e ON e.course_id = c.course_id\n"
            "WHERE e.course_id IS NULL;\n"
            "```"
        ),
        "hint_sql": (
            "-- Courses in the catalog with no enrollments at all\n"
            "SELECT c.course_id, c.title\n"
            "FROM quiz.courses c\n"
            "LEFT JOIN quiz.enrollments e ON e.course_id = c.course_id\n"
            "WHERE e.course_id IS NULL;"
        ),
        "hint_result": {
            "columns": ["course_id", "title"],
            "rows": [["STA601", "Bayesian Statistics"]],
        },
    },
]

assert sum(q["points"] for q in QUESTIONS) == 20
