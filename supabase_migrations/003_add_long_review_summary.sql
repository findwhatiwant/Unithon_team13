alter table message_sessions
add column if not exists summary_text text;

comment on column message_sessions.summary_text is '긴 글 첨삭 기능에서 생성한 자동 요약';
