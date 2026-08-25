import json

import pytest

from refiner.llm import LLMError
from refiner.models import Mode, RefineRequest, RefineResult, Tone
from refiner.pipeline import Pipeline
from refiner.prompts import build_user_prompt


class FakeClient:
    def __init__(self, response: str | None = None, error: Exception | None = None):
        self.response = (
            response
            if response is not None
            else json.dumps({"refined_text": "다듬어진 메시지", "changes": ["오타 수정"]})
        )
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error:
            raise self.error
        return self.response


def make_request(**overrides) -> RefineRequest:
    defaults: dict = dict(text="안녕하세요 오늘 뭐해?", mode=Mode.POLISH)
    defaults.update(overrides)
    return RefineRequest(**defaults)


def test_polish_returns_refined_result():
    result = Pipeline(FakeClient()).run(make_request())

    assert result.success
    assert result.refined_text == "다듬어진 메시지"
    assert result.changes == ["오타 수정"]


def test_empty_text_raises():
    with pytest.raises(ValueError):
        Pipeline(FakeClient()).run(make_request(text="   "))


def test_tone_mode_without_tone_raises():
    with pytest.raises(ValueError):
        Pipeline(FakeClient()).run(make_request(mode=Mode.TONE))


def test_llm_error_becomes_failure_result():
    pipeline = Pipeline(FakeClient(error=LLMError("quota exceeded")))

    result = pipeline.run(make_request())

    assert not result.success
    assert "quota exceeded" in result.error


def test_invalid_json_becomes_failure():
    result = Pipeline(FakeClient(response="not json")).run(make_request())

    assert not result.success
    assert result.error == "응답 파싱 실패"


def test_missing_refined_text_becomes_failure():
    response = json.dumps({"changes": []})
    result = Pipeline(FakeClient(response=response)).run(make_request())

    assert not result.success


def test_empty_refined_text_becomes_failure():
    response = json.dumps({"refined_text": "  ", "changes": []})
    result = Pipeline(FakeClient(response=response)).run(make_request())

    assert not result.success


def test_tone_prompt_includes_tone_label():
    client = FakeClient()
    Pipeline(client).run(make_request(mode=Mode.TONE, tone=Tone.BUSINESS))

    _, user = client.calls[0]
    assert "비즈니스" in user
    assert "어투와 표현만 바꾼다" in user


def test_context_passed_to_prompt():
    client = FakeClient()
    Pipeline(client).run(make_request(context="직속 상사에게 보내는 메시지"))

    _, user = client.calls[0]
    assert "직속 상사에게 보내는 메시지" in user


def test_style_profile_passed_to_prompt():
    client = FakeClient()
    Pipeline(client).run(make_request(style_profile="문장을 짧게 쓰고 ㅋㅋ를 자주 사용함"))

    _, user = client.calls[0]
    assert "[사용자의 평소 말투]" in user
    assert "ㅋㅋ를 자주 사용함" in user


def test_summarize_instruction_in_prompt():
    client = FakeClient()
    Pipeline(client).run(make_request(mode=Mode.SUMMARIZE))

    _, user = client.calls[0]
    assert "간결하게 줄인다" in user


def test_original_text_passed_to_prompt():
    client = FakeClient()
    Pipeline(client).run(make_request(text="내일 3시 회의 잊지마"))

    _, user = client.calls[0]
    assert "내일 3시 회의 잊지마" in user


def test_system_prompt_sent_to_client():
    client = FakeClient()
    Pipeline(client).run(make_request())

    system, _ = client.calls[0]
    assert "JSON 형식으로만 응답" in system


def test_build_user_prompt_section_order():
    prompt = build_user_prompt(
        RefineRequest(
            text="hello",
            mode=Mode.TONE,
            tone=Tone.CASUAL,
            context="친구에게",
        )
    )

    assert prompt.index("[작업]") < prompt.index("[변환할 톤]")
    assert prompt.index("[변환할 톤]") < prompt.index("[상황]")
    assert prompt.index("[상황]") < prompt.index("[원본 메시지]")


def test_failure_factory():
    result = RefineResult.failure("boom")

    assert not result.success
    assert result.error == "boom"
