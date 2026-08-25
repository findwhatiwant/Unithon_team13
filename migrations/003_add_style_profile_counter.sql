-- 마이그레이션 003: 말투 프로필 자동 갱신 추적 컬럼
alter table if exists user_profiles
  add column if not exists style_profile_message_count integer not null default 0;

comment on column user_profiles.style_profile_message_count is '마지막 말투 분석 시점에 DB에 있던 원본 메시지 수';
