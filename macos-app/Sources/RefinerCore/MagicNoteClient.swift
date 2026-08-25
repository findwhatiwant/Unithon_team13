import Foundation

/// Magic Note 피드 스트림용 클라이언트 (/api/compose, /api/mirror)
public struct MagicNoteClient {
    public init() {}

    private var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "apiBaseURL")
        return URL(string: stored ?? "") ?? URL(string: "http://127.0.0.1:8000")!
    }

    // MARK: - 초안 3개 생성

    public struct Candidate: Identifiable, Equatable {
        public let id: String
        public let index: Int
        public let text: String
    }

    public func compose(
        userId: String?,
        context: String,
        purpose: String,
        tone: String?
    ) async throws -> (sessionId: String, candidates: [Candidate]) {
        var body: [String: Any] = [
            "context": context,
            "purpose": purpose,
            "save_history": true,
        ]
        body["user_id"] = userId
        body["tone"] = tone

        let data = try await post(path: "api/compose", body: body)
        struct Response: Decodable {
            let sessionId: String
            let candidates: [CandidateDTO]

            enum CodingKeys: String, CodingKey {
                case sessionId = "session_id"
                case candidates
            }
        }
        struct CandidateDTO: Decodable {
            let candidateId: String
            let candidateIndex: Int
            let candidateText: String

            enum CodingKeys: String, CodingKey {
                case candidateId = "candidate_id"
                case candidateIndex = "candidate_index"
                case candidateText = "candidate_text"
            }
        }
        do {
            let decoded = try JSONDecoder().decode(Response.self, from: data)
            let candidates = decoded.candidates.map {
                Candidate(id: $0.candidateId, index: $0.candidateIndex, text: $0.candidateText)
            }
            return (decoded.sessionId, candidates)
        } catch {
            throw Self.decodeError(data)
        }
    }

    // MARK: - 미러 분석

    public struct MirrorAnalysis {
        public let sessionId: String
        public let intentSummary: String
        public let perceivedTone: String
        public let riskLevel: String
        public let riskReasons: [String]
        public let softRewrite: String
        public let clearRewrite: String
        public let shortRewrite: String
    }

    public func mirror(
        userId: String?,
        sessionId: String?,
        candidateId: String?,
        text: String,
        recipient: String?,
        context: String?,
        purpose: String?,
        tone: String?
    ) async throws -> MirrorAnalysis {
        var body: [String: Any] = [
            "text": text,
            "save_history": true,
        ]
        body["user_id"] = userId
        body["session_id"] = sessionId
        body["candidate_id"] = candidateId
        body["recipient"] = recipient
        body["context"] = context
        body["purpose"] = purpose
        body["tone"] = tone

        let data = try await post(path: "api/mirror", body: body)
        struct Response: Decodable {
            let sessionId: String
            let analysisId: String
            let intentSummary: String
            let perceivedTone: String
            let riskLevel: String
            let riskReasons: [String]
            let softRewrite: String
            let clearRewrite: String
            let shortRewrite: String

            enum CodingKeys: String, CodingKey {
                case sessionId = "session_id"
                case analysisId = "analysis_id"
                case intentSummary = "intent_summary"
                case perceivedTone = "perceived_tone"
                case riskLevel = "risk_level"
                case riskReasons = "risk_reasons"
                case softRewrite = "soft_rewrite"
                case clearRewrite = "clear_rewrite"
                case shortRewrite = "short_rewrite"
            }
        }
        do {
            let r = try JSONDecoder().decode(Response.self, from: data)
            return MirrorAnalysis(
                sessionId: r.sessionId,
                intentSummary: r.intentSummary,
                perceivedTone: r.perceivedTone,
                riskLevel: r.riskLevel,
                riskReasons: r.riskReasons,
                softRewrite: r.softRewrite,
                clearRewrite: r.clearRewrite,
                shortRewrite: r.shortRewrite
            )
        } catch {
            throw Self.decodeError(data)
        }
    }

    private func post(path: String, body: [String: Any]) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 60
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw MagicNoteError.network
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(ErrorBody.self, from: data))?.detail
            throw MagicNoteError.server(message ?? "서버 오류 (\(http.statusCode))")
        }
        return data
    }

    private static func decodeError(_ data: Data) -> Error {
        MagicNoteError.server((try? JSONDecoder().decode(ErrorBody.self, from: data))?.detail ?? "응답 형식 오류")
    }
}

public enum MagicNoteError: LocalizedError {
    case network
    case server(String)

    public var errorDescription: String? {
        switch self {
        case .network:
            return "서버에 연결할 수 없습니다."
        case .server(let detail):
            return detail
        }
    }
}

private struct ErrorBody: Decodable {
    let detail: String?
}
