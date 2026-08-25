create extension if not exists pgcrypto;

create table if not exists user_profiles (
  id uuid primary key default gen_random_uuid(),
  email text,
  nickname text,
  provider text not null default 'anonymous',
  style_profile text,
  style_profile_message_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists user_consents (
  user_id uuid primary key references user_profiles(id) on delete cascade,
  save_message_history boolean not null default false,
  coach_analysis boolean not null default false,
  sensitive_info_storage boolean not null default false,
  consented_at timestamptz,
  revoked_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists message_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references user_profiles(id) on delete set null,
  flow_type text not null,
  source_type text not null default 'direct_input',
  original_text text,
  context text,
  recipient text,
  purpose text,
  tone text,
  input_tone text,
  ai_reason text,
  summary_text text,
  save_history boolean not null default false,
  selected_candidate_id uuid,
  final_text text,
  created_at timestamptz not null default now()
);

create table if not exists compose_candidates (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references message_sessions(id) on delete cascade,
  candidate_index integer not null,
  candidate_text text not null,
  ai_reason text,
  is_selected boolean not null default false,
  created_at timestamptz not null default now(),
  unique (session_id, candidate_index)
);

create table if not exists mirror_analyses (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references message_sessions(id) on delete cascade,
  analyzed_text text,
  intent_summary text,
  perceived_tone text,
  tone_evidence text,
  risk_level text,
  risk_reasons jsonb not null default '[]'::jsonb,
  ai_reason text,
  soft_rewrite text,
  clear_rewrite text,
  short_rewrite text,
  created_at timestamptz not null default now()
);

create table if not exists user_feedbacks (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references message_sessions(id) on delete cascade,
  selected_candidate_id uuid references compose_candidates(id) on delete set null,
  rating text,
  feedback_text text,
  created_at timestamptz not null default now()
);

create table if not exists ai_request_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references user_profiles(id) on delete set null,
  session_id uuid references message_sessions(id) on delete set null,
  feature_type text not null,
  model text,
  success boolean not null,
  error_message text,
  latency_ms integer,
  created_at timestamptz not null default now()
);

create table if not exists correction_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references user_profiles(id) on delete cascade,
  session_id uuid references message_sessions(id) on delete set null,
  change_text text not null,
  created_at timestamptz not null default now()
);

create table if not exists user_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references user_profiles(id) on delete cascade,
  report_date date not null default current_date,
  total_reviews integer not null default 0,
  total_corrections integer not null default 0,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_message_sessions_user_id
  on message_sessions(user_id);

create index if not exists idx_message_sessions_created_at
  on message_sessions(created_at desc);

create index if not exists idx_compose_candidates_session_id
  on compose_candidates(session_id);

create index if not exists idx_mirror_analyses_session_id
  on mirror_analyses(session_id);

create index if not exists idx_correction_log_user
  on correction_log(user_id, created_at desc);

create index if not exists idx_user_reports_user
  on user_reports(user_id, report_date desc);

comment on column user_profiles.style_profile_message_count is '마지막 말투 분석 시점에 DB에 있던 원본 메시지 수';
comment on column message_sessions.input_tone is 'AI가 사용자의 입력문 또는 선택 문장에서 감지한 말투';
comment on column message_sessions.ai_reason is '사용자에게 보여줄 수 있는 AI 판단/추천 근거 요약';
comment on column message_sessions.summary_text is '긴 글 첨삭 기능에서 생성한 자동 요약';
comment on column compose_candidates.ai_reason is 'AI가 이 후보 문장을 추천한 근거';
comment on column mirror_analyses.tone_evidence is 'AI가 해당 말투로 판단한 표현상 근거';
comment on column mirror_analyses.ai_reason is 'Mirror 분석과 수정 제안의 사용자 공개용 근거';
comment on table correction_log is '다듬기 시 변경 요약(changes) 항목별 로그 — 말투 리포트 재료';
comment on table user_reports is '일자별 말투 리포트 스냅샷 (같은 날 재사용)';

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists user_profiles_set_updated_at on user_profiles;
create trigger user_profiles_set_updated_at
before update on user_profiles
for each row execute function set_updated_at();

drop trigger if exists user_consents_set_updated_at on user_consents;
create trigger user_consents_set_updated_at
before update on user_consents
for each row execute function set_updated_at();
