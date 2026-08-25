-- 마이그레이션 004: 교정 로그와 리포트 스냅샷

create table if not exists correction_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references user_profiles(id) on delete cascade,
  session_id uuid references message_sessions(id) on delete set null,
  change_text text not null,
  created_at timestamptz not null default now()
);
create index if not exists idx_correction_log_user on correction_log(user_id, created_at desc);

create table if not exists user_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references user_profiles(id) on delete cascade,
  report_date date not null default current_date,
  total_reviews integer not null default 0,
  total_corrections integer not null default 0,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists idx_user_reports_user on user_reports(user_id, report_date desc);

comment on table correction_log is '다듬기 시 변경 요약(changes) 항목별 로그 — 말투 리포트 재료';
comment on table user_reports is '일자별 말투 리포트 스냅샷 (같은 날 재사용)';
