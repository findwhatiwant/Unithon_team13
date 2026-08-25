from refiner.models import Mode, RefineRequest, Tone

SYSTEM_PROMPT = """너는 한국어 메시지 다듬기 전문가다. 사용자가 보내려는 메시지를 지시에 따라 다듬는다.

규칙:
- 원문의 핵심 의미, 사실, 요청 사항을 절대 바꾸거나 임의로 추가하지 않는다.
- 고유명사, 숫자, 링크, 이모지는 원문 그대로 유지한다.
- 원문이 아무리 길어도 전체를 빠짐없이 처리하며, 내용을 임의로 생략하지 않는다.
- 반드시 아래 JSON 형식으로만 응답한다.
{"refined_text": "다듬어진 메시지", "changes": ["바뀐 점 요약"]}"""

_MODE_INSTRUCTIONS = {
    Mode.POLISH: (
        "맞춤법, 띄어쓰기, 오타, 문법 오류를 교정하고 어색하거나 군더더기인 표현을 자연스러운 한국어로 다듬는다.\n"
        "- 문장이 길거나 중복되면 의미를 유지한 채 읽기 좋게 정리한다.\n"
        "- 나열된 요청사항(일시·장소·요청 등)이 많으면 문단을 나누거나 줄바꿈으로 가독성을 높여도 된다.\n"
        "- 원문의 문체(존댓말/반말), 어투, 감정의 온도는 그대로 유지한다. [사용자 말투]가 주어지면 교정은 하되 "
        "그 사람의 고유한 말투를 최대한 살린다."
    ),
    Mode.TONE: (
        "메시지의 내용은 하나도 빠뜨리지 않고 유지한 채, 지정된 톤에 맞게 어투와 표현만 바꾼다.\n"
        "- 인사말/끝맺음은 톤에 어울리게 보강할 수 있다.\n"
        "- 원문의 핵심 요청과 정보(일시, 장소, 수치 등)는 정확히 보존한다."
    ),
    Mode.SUMMARIZE: (
        "메시지를 핵심만 남겨 간결하게 줄인다.\n"
        "- 상대방이 반드시 알아야 할 필수 정보(일시, 장소, 금액, 마감 기한, 요청 사항, 다음 액션)는 절대 빠뜨리지 않는다.\n"
        "- 사족, 반복 표현, 완곐구는 제거한다.\n"
        "- 필요하면 줄바꿈이나 불릿으로 구조화해 한눈에 보이게 한다."
    ),
}

_TONE_LABELS = {
    Tone.FORMAL: "존댓말 (정중한 공손체)",
    Tone.CASUAL: "반말 (친한 친구에게 하는 말투)",
    Tone.BUSINESS: "비즈니스 (격식 있는 업무용 어투)",
    Tone.FRIENDLY: "친근함 (밝고 부드러운 어투)",
}


def build_user_prompt(request: RefineRequest) -> str:
    parts = [f"[작업]\n{_MODE_INSTRUCTIONS[request.mode]}"]
    if request.mode is Mode.TONE:
        parts.append(f"[변환할 톤]\n{_TONE_LABELS[request.tone]}")
    if request.style_profile:
        parts.append(f"[사용자의 평소 말투]\n{request.style_profile}")
    if request.context:
        parts.append(f"[상황]\n{request.context}")
    parts.append(f"[원본 메시지]\n{request.text}")
    return "\n\n".join(parts)
