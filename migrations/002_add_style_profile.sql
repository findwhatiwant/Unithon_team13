-- 마이그레이션 002: 사용자 말투 프로필 추가
-- 실행 위치: Supabase 대시보드 -> SQL Editor

alter table if exists user_profiles
  add column if not exists style_profile text;

comment on column user_profiles.style_profile is 'LLM이 분석한 사용자 고유 말투 요약 (analyze API가 갱신)';
