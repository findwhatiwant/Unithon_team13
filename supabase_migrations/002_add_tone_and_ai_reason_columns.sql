alter table message_sessions
add column if not exists input_tone text,
add column if not exists ai_reason text;

alter table compose_candidates
add column if not exists ai_reason text;

alter table mirror_analyses
add column if not exists tone_evidence text,
add column if not exists ai_reason text;

comment on column message_sessions.input_tone is 'AI가 사용자의 입력문 또는 선택 문장에서 감지한 말투';
comment on column message_sessions.ai_reason is '사용자에게 보여줄 수 있는 AI 판단/추천 근거 요약';
comment on column compose_candidates.ai_reason is 'AI가 이 후보 문장을 추천한 근거';
comment on column mirror_analyses.tone_evidence is 'AI가 해당 말투로 판단한 표현상 근거';
comment on column mirror_analyses.ai_reason is 'Mirror 분석과 수정 제안의 사용자 공개용 근거';
