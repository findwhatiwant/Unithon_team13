import json

from refiner.llm import LLMClient
from refiner.models import Mode, RefineRequest, RefineResult
from refiner.prompts import SYSTEM_PROMPT, build_user_prompt


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
            changes = [str(change) for change in data.get("changes", [])]
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
