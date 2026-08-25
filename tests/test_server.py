import json

from refiner.server import (
    ComposeRequest,
    LongReviewRequest,
    MirrorRequest,
    ReportResponse,
    _cluster_corrections,
    _generate_compose_candidates,
    _generate_long_review,
    _generate_mirror_analysis,
    _generate_style_profile,
    _insert_correction_logs,
    _insert_with_optional_columns,
    _llm_error_response,
    _log_corrections,
    _report_payload,
    _should_save_history,
    _update_with_optional_columns,
)
from refiner.supabase_store import SupabaseError


class FakeClient:
    def __init__(self, response: dict):
        self.response = json.dumps(response, ensure_ascii=False)

    def generate(self, system: str, user: str) -> str:
        return self.response


class SchemaCacheStore:
    def __init__(self):
        self.insert_payloads: list[dict] = []
        self.update_payloads: list[dict] = []

    def insert(self, table: str, payload: dict) -> dict:
        self.insert_payloads.append(payload)
        if "ai_reason" in payload or "summary_text" in payload:
            raise SupabaseError(
                "Supabase HTTP 400: Could not find the 'ai_reason' column of "
                "'message_sessions' in the schema cache"
            )
        return {"id": "session-1"}

    def update(self, table: str, payload: dict, filters: dict[str, str]) -> list[dict]:
        self.update_payloads.append(payload)
        if "ai_reason" in payload:
            raise SupabaseError(
                "Supabase HTTP 400: Could not find the 'ai_reason' column of "
                "'message_sessions' in the schema cache"
            )
        return [{"id": "session-1"}]


class CorrectionLogStore:
    def __init__(self):
        self.table: str | None = None
        self.payload: list[dict] = []

    def bulk_insert(self, table: str, payload: list[dict]) -> list[dict]:
        self.table = table
        self.payload = payload
        return payload


def test_save_history_requires_user_id():
    assert _should_save_history("user-1", True)
    assert not _should_save_history(None, True)
    assert not _should_save_history("user-1", False)


def test_insert_retries_without_optional_columns_when_supabase_schema_is_old():
    store = SchemaCacheStore()

    row = _insert_with_optional_columns(
        store,
        "message_sessions",
        {
            "flow_type": "direct_mirror",
            "input_tone": "부드러움",
            "ai_reason": "근거",
            "summary_text": "요약",
        },
    )

    assert row["id"] == "session-1"
    assert store.insert_payloads[-1] == {"flow_type": "direct_mirror"}


def test_update_retries_without_optional_columns_when_supabase_schema_is_old():
    store = SchemaCacheStore()

    rows = _update_with_optional_columns(
        store,
        "message_sessions",
        {"save_history": True, "input_tone": "부드러움", "ai_reason": "근거"},
        {"id": "eq.session-1"},
    )

    assert rows == [{"id": "session-1"}]
    assert store.update_payloads[-1] == {"save_history": True}


def test_compose_candidates_include_ai_reason():
    client = FakeClient(
        {
            "candidates": [
                {"text": "첫 번째 문장", "strategy": "부담이 적은 표현"},
                {"text": "두 번째 문장", "ai_reason": "정중한 표현"},
                {"text": "세 번째 문장", "strategy": "짧고 명확함"},
            ]
        }
    )

    candidates = _generate_compose_candidates(
        client,
        ComposeRequest(context="회의 시간을 바꾸고 싶음"),
    )

    assert candidates[0]["ai_reason"] == "부담이 적은 표현"
    assert candidates[1]["ai_reason"] == "정중한 표현"


def test_mirror_analysis_includes_tone_evidence_and_ai_reason():
    client = FakeClient(
        {
            "intent_summary": "일정 변경 요청",
            "perceived_tone": "조심스럽지만 급한 말투",
            "tone_evidence": "'지금 바로'라는 표현이 급하게 읽힐 수 있음",
            "risk_level": "보통",
            "risk_reasons": ["상대 일정 부담을 줄 수 있음"],
            "ai_reason": "요청 의도는 명확하지만 완충 표현이 필요함",
            "soft_rewrite": "혹시 가능하다면 회의 시간을 조정할 수 있을까요?",
            "clear_rewrite": "내일 회의 시간을 3시로 바꿀 수 있을까요?",
            "short_rewrite": "내일 회의 시간 변경 가능할까요?",
        }
    )

    analysis = _generate_mirror_analysis(
        client,
        MirrorRequest(text="지금 바로 회의 시간 바꿔 주세요"),
    )

    assert analysis["tone_evidence"] == "'지금 바로'라는 표현이 급하게 읽힐 수 있음"
    assert analysis["ai_reason"] == "요청 의도는 명확하지만 완충 표현이 필요함"


def test_long_review_returns_edited_text_and_summary():
    client = FakeClient(
        {
            "edited_text": "첨삭된 긴 글입니다.",
            "summary_text": "핵심 내용을 짧게 요약했습니다.",
            "key_points": ["첫 번째 핵심", "두 번째 핵심"],
            "changes": ["문장을 자연스럽게 수정", "중복 표현 제거"],
            "ai_reason": "의미는 유지하고 가독성을 높였습니다.",
        }
    )

    result = _generate_long_review(
        client,
        LongReviewRequest(text="원래 긴 글입니다.", document_type="블로그"),
    )

    assert result["edited_text"] == "첨삭된 긴 글입니다."
    assert result["summary_text"] == "핵심 내용을 짧게 요약했습니다."
    assert result["key_points"] == ["첫 번째 핵심", "두 번째 핵심"]
    assert result["changes"] == ["문장을 자연스럽게 수정", "중복 표현 제거"]


def test_generate_style_profile_returns_profile_text():
    client = FakeClient(
        {
            "style_profile": "짧은 존댓말을 주로 쓰고 완곡한 표현을 자주 사용함",
        }
    )

    profile = _generate_style_profile(client, ["안녕하세요. 확인 부탁드려요.", "혹시 가능할까요?"])

    assert profile == "짧은 존댓말을 주로 쓰고 완곡한 표현을 자주 사용함"


def test_log_corrections_writes_each_change_text():
    store = CorrectionLogStore()

    _log_corrections(store, "user-1", "session-1", ["문장 정리", "  ", "오타 수정"])

    assert store.table == "correction_log"
    assert store.payload == [
        {"user_id": "user-1", "session_id": "session-1", "change_text": "문장 정리"},
        {"user_id": "user-1", "session_id": "session-1", "change_text": "오타 수정"},
    ]


def test_log_corrections_skips_without_user_id():
    store = CorrectionLogStore()

    _log_corrections(store, None, "session-1", ["문장 정리"])

    assert store.table is None
    assert store.payload == []


def test_insert_correction_logs_allows_missing_session_id():
    store = CorrectionLogStore()

    rows = _insert_correction_logs(store, "user-1", None, ["문장 정리"])

    assert rows == [
        {"user_id": "user-1", "session_id": None, "change_text": "문장 정리"},
    ]


def test_cluster_corrections_returns_report_sections():
    client = FakeClient(
        {
            "top_mistakes": [
                {
                    "label": "명령형 표현",
                    "count": 2,
                    "example_before": "해줘",
                    "example_after": "해주실 수 있을까요",
                }
            ],
            "tone_habits": ["요청을 짧게 쓰는 편"],
            "suggestions": ["상대에게 선택권을 주는 표현을 추가하기"],
        }
    )

    report = _cluster_corrections(client, ["명령형을 완곡한 표현으로 변경"], "짧은 존댓말")

    assert report["top_mistakes"][0]["label"] == "명령형 표현"
    assert report["tone_habits"] == ["요청을 짧게 쓰는 편"]


def test_report_payload_excludes_generated_at():
    payload = _report_payload(
        ReportResponse(
            total_reviews=3,
            total_corrections=2,
            top_mistakes=[{"label": "명령형 표현", "count": 2}],
            generated_at="2026-08-26T00:00:00Z",
        )
    )

    assert payload["total_reviews"] == 3
    assert payload["top_mistakes"][0]["label"] == "명령형 표현"
    assert "generated_at" not in payload


def test_llm_quota_error_returns_429_message():
    status_code, detail = _llm_error_response("429 RESOURCE_EXHAUSTED quota exceeded")

    assert status_code == 429
    assert "Gemini 사용량 제한" in detail


def test_llm_unknown_error_returns_503_message():
    status_code, detail = _llm_error_response("temporary model failure")

    assert status_code == 503
    assert "AI 호출에 실패" in detail
