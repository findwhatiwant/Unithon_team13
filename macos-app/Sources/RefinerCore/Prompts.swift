public enum Prompts {
    public static let systemPrompt = """
    너는 한국어 메시지 다듬기 전문가다. 사용자가 보내려는 메시지를 지시에 따라 다듬는다.

    규칙:
    - 원문의 핵심 의미, 사실, 요청 사항을 절대 바꾸거나 임의로 추가하지 않는다.
    - 고유명사, 숫자, 링크, 이모지는 원문 그대로 유지한다.
    - 반드시 아래 JSON 형식으로만 응답한다.
    {"refined_text": "다듬어진 메시지", "changes": ["바뀐 점 요약"]}
    """

    private static let modeInstructions: [Mode: String] = [
        .polish: """
        맞춤법, 띄어쓰기, 오타를 교정하고 어색한 문장을 자연스럽게 다듬는다.
        문체와 어투는 원문 그대로 유지한다.
        """,
        .tone: "메시지를 지정된 톤으로 변환한다. 내용은 유지하고 어투만 바꾼다.",
        .summarize: """
        메시지를 핵심 내용만 남겨 간결하게 줄인다. 상대방이 알아야 할 필수 정보(일시, 장소, 요청 사항 등)는 빠뜨리지 않는다.
        """,
    ]

    private static let toneLabels: [Tone: String] = [
        .formal: "존댓말 (정중한 공손체)",
        .casual: "반말 (친한 친구에게 하는 말투)",
        .business: "비즈니스 (격식 있는 업무용 어투)",
        .friendly: "친근함 (밝고 부드러운 어투)",
    ]

    public static func buildUserPrompt(_ request: RefineRequest) -> String {
        var parts: [String] = []
        parts.append("[작업]\n\(modeInstructions[request.mode]!)")
        if request.mode == .tone, let tone = request.tone {
            parts.append("[변환할 톤]\n\(toneLabels[tone]!)")
        }
        if let context = request.context, !context.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            parts.append("[상황]\n\(context)")
        }
        parts.append("[원본 메시지]\n\(request.text)")
        return parts.joined(separator: "\n\n")
    }
}
