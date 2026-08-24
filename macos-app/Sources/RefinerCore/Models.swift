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
