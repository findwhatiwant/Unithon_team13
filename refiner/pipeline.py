import json

from refiner.llm import LLMClient
from refiner.models import Mode, RefineRequest, RefineResult
from refiner.prompts import SYSTEM_PROMPT, build_user_prompt


_CHANGE_KEYS = ("original", "corrected", "reason", "summary")


class Pipeline:
    def __init__(self, client: LLMClient):
        self._client = client

    def run(self, request: RefineRequest) -> RefineResult:
        self._validate(request)
        try:
            raw = self._client.generate(SYSTEM_PROMPT, build_user_prompt(request))
        except Exception as exc:
            return RefineResult.failure(f"LLM 호출 실패: {exc}")
        try:
            data = json.loads(raw)
            refined_text = str(data["refined_text"]).strip()
            changes = _normalize_changes(data.get("changes", []))
        except (json.JSONDecodeError, KeyError, TypeError):
            return RefineResult.failure("응답 파싱 실패")
        if not refined_text:
            return RefineResult.failure("빈 결과 반환")
        return RefineResult(refined_text=refined_text, changes=changes)

    @staticmethod
    def _validate(request: RefineRequest) -> None:
        if not request.text.strip():
            raise ValueError("text는 비어 있을 수 없습니다.")
        if request.mode is Mode.TONE and request.tone is None:
            raise ValueError("mode=TONE에는 tone 지정이 필요합니다.")


def _normalize_changes(raw: object) -> list[dict[str, str]]:
    """LLM 응답의 changes를 {original, corrected, reason} 또는 {summary} 형태로 통일한다."""
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw[:30]:
        change = _normalize_change(item)
        if change:
            normalized.append(change)
    return normalized


def _normalize_change(item: object) -> dict[str, str] | None:
    if isinstance(item, dict):
        change = {
            key: value.strip()
            for key in _CHANGE_KEYS
            if isinstance((value := item.get(key)), str) and value.strip()
        }
        return change or None
    if isinstance(item, str) and item.strip():
        return {"summary": item.strip()}
    return None
