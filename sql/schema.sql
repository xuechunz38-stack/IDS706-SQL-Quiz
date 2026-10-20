-- Schema for the SQL quiz.
-- quiz.*  : the dataset quiz takers query (read-only for them)
-- app.*   : questions, saved answers and the audit log (never visible to takers)
-- Neither schema is exposed through Supabase's REST API (only "public" is).

-- ---------------------------------------------------------------- dataset
drop schema if exists quiz cascade;
create schema quiz;

create table quiz.students (
    student_id  integer primary key,
    full_name   text    not null,
    program     text    not null,          -- MIDS, MEM, MBA
    start_year  integer not null
);

create table quiz.courses (
    course_id   text    primary key,       -- e.g. IDS706
    title       text    not null,
    department  text    not null,          -- IDS, ENG, FUQ, STA
    credits     integer not null
);

create table quiz.enrollments (
    student_id  integer      not null references quiz.students,
    course_id   text         not null references quiz.courses,
    semester    text         not null,     -- 'Fall 2026', 'Spring 2026'
    grade       numeric(4,1) not null check (grade between 0 and 100),
    primary key (student_id, course_id, semester)
);

-- ------------------------------------------------------------- app tables
create schema if not exists app;

create table if not exists app.questions (
    id          integer primary key,
    title       text    not null,
    prompt      text    not null,
    points      integer not null check (points > 0),
    hint_sql    text    not null,
    hint_result jsonb   not null           -- {"columns": [...], "rows": [[...], ...]}
);

create table if not exists app.saved_answers (
    id          bigserial   primary key,
    user_id     uuid        not null,
    user_email  text        not null,
    question_id integer     not null references app.questions,
    sql_text    text        not null,
    saved_at    timestamptz not null default now()
);

create table if not exists app.audit_log (
    id          bigserial   primary key,
    user_id     uuid        not null,
    user_email  text        not null,
    action      text        not null check (action in ('run', 'save')),
    question_id integer,
    sql_text    text        not null,
    row_count   integer,
    success     boolean     not null,
    error       text,
    created_at  timestamptz not null default now(),
    prev_hash   text        not null,
    row_hash    text        not null
);

-- Supabase best practice: RLS on everything. The app roles below get explicit
-- policies; anything else (anon, authenticated, quiz_taker) sees nothing.
alter table app.questions     enable row level security;
alter table app.saved_answers enable row level security;
alter table app.audit_log     enable row level security;

-- ------------------------------------------- audit log integrity (hash chain)
-- Each row stores the hash of the previous row, so editing or deleting any
-- historical row breaks the chain and scripts/check_db.py fails in CI.
create or replace function app.audit_row_hash(
    p_prev text, p_user uuid, p_email text, p_action text, p_question integer,
    p_sql text, p_rows integer, p_success boolean, p_error text, p_at timestamptz
) returns text language sql immutable as $$
    select encode(sha256(convert_to(concat_ws('|',
        p_prev, p_user::text, p_email, p_action, p_question::text, p_sql,
        p_rows::text, p_success::text, p_error,
        to_char(p_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')
    ), 'UTF8')), 'hex')
$$;

create or replace function app.audit_chain() returns trigger
language plpgsql security definer set search_path = app, pg_temp as $$
declare
    prev text;
begin
    perform pg_advisory_xact_lock(706);
    select row_hash into prev from app.audit_log order by id desc limit 1;
    new.prev_hash  := coalesce(prev, 'GENESIS');
    new.created_at := now();
    new.row_hash   := app.audit_row_hash(new.prev_hash, new.user_id, new.user_email,
        new.action, new.question_id, new.sql_text, new.row_count, new.success,
        new.error, new.created_at);
    return new;
end $$;

create or replace function app.audit_append_only() returns trigger
language plpgsql as $$
begin
    raise exception 'app.audit_log is append-only (% blocked)', tg_op;
end $$;

drop trigger if exists audit_chain on app.audit_log;
create trigger audit_chain before insert on app.audit_log
    for each row execute function app.audit_chain();

drop trigger if exists audit_no_update on app.audit_log;
create trigger audit_no_update before update or delete on app.audit_log
    for each row execute function app.audit_append_only();

drop trigger if exists audit_no_truncate on app.audit_log;
create trigger audit_no_truncate before truncate on app.audit_log
    for each statement execute function app.audit_append_only();
