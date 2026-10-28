"""Knowledge that goes into the vector database.

Schema documents are built from the live database (see rag.schema_documents);
the business rules and few-shot examples below are written by hand. The
few-shot questions are deliberately different from the five quiz questions.
"""

BUSINESS_RULES = [
    ("rule_schema_prefix",
     "All quiz tables live in the schema named quiz. Always write quiz.students, "
     "quiz.courses and quiz.enrollments, never the bare table name."),
    ("rule_program",
     "students.program is the degree program: 'MIDS' (Master in Interdisciplinary Data "
     "Science), 'MEM' (Master of Engineering Management) or 'MBA'. Filter with "
     "program = 'MIDS' using the exact uppercase code."),
    ("rule_start_year",
     "students.start_year is the year a student started the program, e.g. 2025 or 2026. "
     "'Started in 2025' means start_year = 2025."),
    ("rule_semester",
     "enrollments.semester is text such as 'Fall 2026' or 'Spring 2026'. Filter with "
     "semester = 'Fall 2026'. There is no separate year or term column."),
    ("rule_grade",
     "enrollments.grade is a numeric score from 0 to 100 for one student in one course "
     "in one semester. Average grade means AVG(grade); round with ROUND(AVG(grade), 1) "
     "when one decimal place is asked for."),
    ("rule_department",
     "courses.department is the owning department code: 'IDS', 'ENG', 'FUQ' (Fuqua "
     "business school) or 'STA'. Grades by department need a join from enrollments to "
     "courses on course_id."),
    ("rule_counting_students",
     "A student can appear in enrollments more than once (several courses or semesters). "
     "To count students per course use COUNT(DISTINCT e.student_id). To count how many "
     "courses a student takes use COUNT(*) grouped by the student."),
    ("rule_having",
     "Conditions on an aggregate such as 'at least 3 courses' or 'more than 2 students' "
     "go in HAVING, e.g. HAVING COUNT(*) >= 3, not in WHERE."),
    ("rule_no_enrollments",
     "Courses with no enrollments (or students with no enrollments) are found with a "
     "LEFT JOIN to enrollments and WHERE e.course_id IS NULL (anti-join). An inner JOIN "
     "drops those rows."),
    ("rule_names",
     "Student names are in students.full_name as one column such as 'Ava Chen'. There is "
     "no first_name or last_name column. Course names are in courses.title."),
    ("rule_ordering",
     "When the question says 'alphabetical' use ORDER BY the name column ascending. "
     "'Most' or 'highest' means ORDER BY ... DESC. Break ties with a second sort key "
     "when the question names one."),
    ("rule_read_only",
     "Generate exactly one read-only SELECT (or WITH ... SELECT) statement for "
     "PostgreSQL. Never INSERT, UPDATE, DELETE, DROP or create objects."),
]

FEW_SHOT_EXAMPLES = [
    ("Which MEM students started in 2026?",
     "SELECT full_name\nFROM quiz.students\nWHERE program = 'MEM' AND start_year = 2026\n"
     "ORDER BY full_name;"),
    ("List all courses worth 3 credits in the IDS department.",
     "SELECT course_id, title\nFROM quiz.courses\nWHERE department = 'IDS' AND credits = 3\n"
     "ORDER BY course_id;"),
    ("How many students are in each program?",
     "SELECT program, COUNT(*) AS n_students\nFROM quiz.students\nGROUP BY program\n"
     "ORDER BY n_students DESC;"),
    ("What is the average grade in each course, rounded to 1 decimal?",
     "SELECT e.course_id, ROUND(AVG(e.grade), 1) AS avg_grade\nFROM quiz.enrollments e\n"
     "GROUP BY e.course_id\nORDER BY avg_grade DESC;"),
    ("How many distinct students took a course in Spring 2026, per department?",
     "SELECT c.department, COUNT(DISTINCT e.student_id) AS n_students\n"
     "FROM quiz.enrollments e\nJOIN quiz.courses c ON c.course_id = e.course_id\n"
     "WHERE e.semester = 'Spring 2026'\nGROUP BY c.department\nORDER BY n_students DESC;"),
    ("Which courses have more than 4 enrollments?",
     "SELECT course_id, COUNT(*) AS n_enrollments\nFROM quiz.enrollments\n"
     "GROUP BY course_id\nHAVING COUNT(*) > 4\nORDER BY n_enrollments DESC;"),
    ("Which students have no enrollments at all?",
     "SELECT s.student_id, s.full_name\nFROM quiz.students s\n"
     "LEFT JOIN quiz.enrollments e ON e.student_id = s.student_id\n"
     "WHERE e.student_id IS NULL;"),
    ("Show each MBA student's grades with the course title.",
     "SELECT s.full_name, c.title, e.semester, e.grade\nFROM quiz.students s\n"
     "JOIN quiz.enrollments e ON e.student_id = s.student_id\n"
     "JOIN quiz.courses c ON c.course_id = e.course_id\nWHERE s.program = 'MBA'\n"
     "ORDER BY s.full_name, c.title;"),
    ("Who got the highest grade in IDS702?",
     "SELECT s.full_name, e.grade\nFROM quiz.enrollments e\n"
     "JOIN quiz.students s ON s.student_id = e.student_id\nWHERE e.course_id = 'IDS702'\n"
     "AND e.grade = (SELECT MAX(grade) FROM quiz.enrollments WHERE course_id = 'IDS702');"),
    ("How many credits is each student taking in Fall 2026?",
     "SELECT s.full_name, SUM(c.credits) AS total_credits\nFROM quiz.students s\n"
     "JOIN quiz.enrollments e ON e.student_id = s.student_id\n"
     "JOIN quiz.courses c ON c.course_id = e.course_id\nWHERE e.semester = 'Fall 2026'\n"
     "GROUP BY s.full_name\nORDER BY total_credits DESC, s.full_name;"),
]
