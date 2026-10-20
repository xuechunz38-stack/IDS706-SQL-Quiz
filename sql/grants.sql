-- Privileges for the two runtime roles (created by scripts/seed.py).
--   quiz_taker : runs the SQL that quiz takers type. Read-only, quiz.* only.
--   quiz_app   : used by the web app to read questions and append saves/audit rows.

revoke all on schema quiz, app from public;

grant usage  on schema quiz to quiz_taker;
grant select on all tables in schema quiz to quiz_taker;
alter role quiz_taker set default_transaction_read_only = on;
alter role quiz_taker set statement_timeout = '5s';

grant usage on schema app to quiz_app;
grant select         on app.questions                     to quiz_app;
grant select, insert on app.saved_answers, app.audit_log  to quiz_app;
grant usage on sequence app.saved_answers_id_seq, app.audit_log_id_seq to quiz_app;
-- No UPDATE / DELETE / TRUNCATE for anyone but the owner, and the triggers in
-- schema.sql block those for the owner too.
revoke update, delete, truncate on app.audit_log from quiz_app, quiz_taker;
alter role quiz_app set statement_timeout = '5s';

drop policy if exists app_read_questions on app.questions;
create policy app_read_questions on app.questions for select to quiz_app using (true);

drop policy if exists app_read_answers on app.saved_answers;
create policy app_read_answers on app.saved_answers for select to quiz_app using (true);
drop policy if exists app_insert_answers on app.saved_answers;
create policy app_insert_answers on app.saved_answers for insert to quiz_app with check (true);

drop policy if exists app_read_audit on app.audit_log;
create policy app_read_audit on app.audit_log for select to quiz_app using (true);
drop policy if exists app_insert_audit on app.audit_log;
create policy app_insert_audit on app.audit_log for insert to quiz_app with check (true);
