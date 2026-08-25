import Foundation

public enum Mode: String, CaseIterable, Identifiable {
    case polish
    case tone
    case summarize

    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .polish: return "교정"
        case .tone: return "톤"
        case .summarize: return "요약"
        }
    }
}

public enum Tone: String, CaseIterable, Identifiable {
    case formal
    case casual
    case business
    case friendly

    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .formal: return "존댓말"
        case .casual: return "반말"
        case .business: return "비즈니스"
        case .friendly: return "친근함"
        }
    }
}

public enum RefineError: Error, Equatable {
    case emptyText
    case toneRequired
    case missingAPIKey
    case rateLimited
    case unauthorized
    case apiFailed(String)
    case network(String)
    case parsingFailed(String)
    case emptyResult

    public var message: String {
        switch self {
        case .emptyText:
            return "메시지를 입력해주세요."
        case .toneRequired:
            return "톤을 선택해주세요."
        case .missingAPIKey:
            return "API 키를 설정해주세요."
        case .rateLimited:
            return "무료 한도를 초과했습니다. 내일 다시 시도해주세요."
        case .unauthorized:
            return "API 키가 올바르지 않습니다. 설정에서 확인해주세요."
        case .apiFailed(let detail):
            return "요청 실패: \(detail)"
        case .network(let detail):
            return "네트워크 오류: \(detail)"
        case .parsingFailed(let detail):
            return "응답 파싱 실패: \(detail)"
        case .emptyResult:
            return "빈 결과가 반환되었습니다."
        }
    }
}

public struct RefineRequest: Equatable {
    public var text: String
    public var mode: Mode
    public var tone: Tone?
    public var context: String?

    public init(text: String, mode: Mode = .polish, tone: Tone? = nil, context: String? = nil) {
        self.text = text
        self.mode = mode
        self.tone = tone
        self.context = context
    }

    public func validate() throws {
        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw RefineError.emptyText
        }
        if mode == .tone && tone == nil {
            throw RefineError.toneRequired
        }
    }
}

public struct RefineResult: Equatable {
    public var refinedText: String
    public var changes: [String]

    public init(refinedText: String, changes: [String] = []) {
        self.refinedText = refinedText
        self.changes = changes
    }
}

/// changes 항목은 서버·LLM에 따라 문자열 요약 또는 {original, corrected, reason} 객체로 온다.
public struct FlexibleChange: Decodable, Equatable {
    public let original: String?
    public let corrected: String?
    public let reason: String?
    public let summary: String?

    public init(original: String? = nil, corrected: String? = nil, reason: String? = nil, summary: String? = nil) {
        func clean(_ value: String?) -> String? {
            guard let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else {
                return nil
            }
            return trimmed
        }
        self.original = clean(original)
        self.corrected = clean(corrected)
        self.reason = clean(reason)
        self.summary = clean(summary)
    }

    public init(any value: Any) {
        if let text = value as? String {
            self.init(summary: text)
            return
        }
        if let dict = value as? [String: Any] {
            self.init(
                original: dict["original"] as? String,
                corrected: dict["corrected"] as? String,
                reason: dict["reason"] as? String,
                summary: dict["summary"] as? String
            )
            return
        }
        self.init()
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let text = try? container.decode(String.self) {
            self.init(summary: text)
            return
        }
        let dict = try? container.decode([String: String].self)
        self.init(
            original: dict?["original"],
            corrected: dict?["corrected"],
            reason: dict?["reason"],
            summary: dict?["summary"]
        )
    }

    /// 목록 카드에 표시할 텍스트.
    public var displayText: String {
        if let original, let corrected { return "\(original) → \(corrected)" }
        if let summary { return summary }
        if let original { return original }
        if let corrected { return corrected }
        return "교정 항목"
    }

    /// 다듬어진 결과에서 위치를 찾을 때 쓰는 기준 문자열. corrected 우선.
    public var locator: String? {
        corrected ?? original ?? parsedSummaryLocator
    }

    /// 구조화 필드가 없는 경우, 문자열 요약("... 교정 ('A' -> 'B')")에서 수정 후 표현을 추출한다.
    private var parsedSummaryLocator: String? {
        guard let summary,
              let arrow = summary.range(of: "->") ?? summary.range(of: "→") else {
            return nil
        }
        var tail = String(summary[arrow.upperBound...]).trimmingCharacters(in: .whitespaces)
        while tail.hasSuffix(")") || tail.hasSuffix("}") {
            tail.removeLast()
            tail = tail.trimmingCharacters(in: .whitespaces)
        }
        for quote in ["'", "\"", "\u{2018}", "\u{201C}", "「"] where tail.hasPrefix(quote) {
            tail.removeFirst()
            break
        }
        for quote in ["'", "\"", "\u{2019}", "\u{201D}", "」"] where tail.hasSuffix(quote) {
            tail.removeLast()
            break
        }
        let cleaned = tail.trimmingCharacters(in: .whitespaces)
        return cleaned.isEmpty ? nil : cleaned
    }
}

public enum ChangeNormalizer {
    /// [Any] 형태의 changes를 사람이 읽는 문자열 배열로 통일한다.
    public static func displayStrings(from raw: [Any]?) -> [String] {
        guard let raw else { return [] }
        return raw.map(FlexibleChange.init(any:)).map(\.displayText)
    }
}
