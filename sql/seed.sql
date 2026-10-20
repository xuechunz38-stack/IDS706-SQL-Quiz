-- Dataset: a small slice of graduate course enrollments.

insert into quiz.students (student_id, full_name, program, start_year) values
    (1,  'Ava Chen',    'MIDS', 2025),
    (2,  'Ben Okafor',  'MIDS', 2025),
    (3,  'Carla Diaz',  'MEM',  2025),
    (4,  'Dev Patel',   'MIDS', 2026),
    (5,  'Emma Rossi',  'MBA',  2026),
    (6,  'Felix Wang',  'MEM',  2026),
    (7,  'Grace Kim',   'MIDS', 2026),
    (8,  'Hiro Tanaka', 'MBA',  2025),
    (9,  'Isla Novak',  'MIDS', 2025),
    (10, 'Jamal Reed',  'MEM',  2026);

insert into quiz.courses (course_id, title, department, credits) values
    ('IDS706',  'Data Engineering Systems',            'IDS', 3),
    ('IDS702',  'Modeling and Representation of Data', 'IDS', 3),
    ('IDS705',  'Machine Learning Practice',           'IDS', 3),
    ('MENG570', 'Business Fundamentals for Engineers', 'ENG', 3),
    ('ENG540',  'Product Design',                      'ENG', 2),
    ('MBA510',  'Managerial Economics',                'FUQ', 3),
    ('STA601',  'Bayesian Statistics',                 'STA', 3);

insert into quiz.enrollments (student_id, course_id, semester, grade) values
    (1,  'IDS706',  'Fall 2026',   92.0),
    (1,  'IDS702',  'Fall 2026',   88.0),
    (1,  'IDS705',  'Fall 2026',   95.0),
    (1,  'MENG570', 'Spring 2026', 85.0),
    (2,  'IDS706',  'Fall 2026',   78.0),
    (2,  'IDS705',  'Fall 2026',   84.0),
    (2,  'MBA510',  'Spring 2026', 90.0),
    (3,  'MENG570', 'Fall 2026',   91.0),
    (3,  'ENG540',  'Fall 2026',   87.0),
    (3,  'IDS706',  'Fall 2026',   81.0),
    (4,  'IDS706',  'Fall 2026',   95.0),
    (4,  'IDS702',  'Fall 2026',   90.0),
    (4,  'ENG540',  'Fall 2026',   79.0),
    (4,  'IDS705',  'Spring 2026', 88.0),
    (5,  'MBA510',  'Fall 2026',   93.0),
    (5,  'MENG570', 'Fall 2026',   76.0),
    (6,  'ENG540',  'Spring 2026', 82.0),
    (6,  'MENG570', 'Fall 2026',   89.0),
    (7,  'IDS706',  'Fall 2026',   88.0),
    (7,  'IDS702',  'Fall 2026',   94.0),
    (7,  'IDS705',  'Fall 2026',   91.0),
    (7,  'MBA510',  'Fall 2026',   85.0),
    (8,  'MBA510',  'Spring 2026', 80.0),
    (8,  'IDS706',  'Fall 2026',   72.0),
    (9,  'IDS702',  'Spring 2026', 86.0),
    (9,  'IDS705',  'Fall 2026',   89.0),
    (10, 'ENG540',  'Fall 2026',   90.0);
