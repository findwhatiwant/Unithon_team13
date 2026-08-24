create extension if not exists pgcrypto;

create table if not exists user_profiles (
  id uuid primary key default gen_random_uuid(),
  email text,
  nickname text,
  provider text not null default 'anonymous',
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
  risk_level text,
  risk_reasons jsonb not null default '[]'::jsonb,
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

create index if not exists idx_message_sessions_user_id
  on message_sessions(user_id);

create index if not exists idx_message_sessions_created_at
  on message_sessions(created_at desc);

create index if not exists idx_compose_candidates_session_id
  on compose_candidates(session_id);

create index if not exists idx_mirror_analyses_session_id
  on mirror_analyses(session_id);

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
