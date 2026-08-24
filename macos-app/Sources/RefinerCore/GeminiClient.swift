import Foundation

public protocol RefiningService {
    func refine(_ request: RefineRequest) async throws -> RefineResult
}

public enum ResultParser {
    public static func parse(_ raw: String) throws -> RefineResult {
        let cleaned = stripFences(raw)
        guard let data = cleaned.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data),
              let dictionary = object as? [String: Any] else {
            throw RefineError.parsingFailed("JSON이 아닌 응답")
        }
        guard let refinedText = dictionary["refined_text"] as? String else {
            throw RefineError.parsingFailed("refined_text 누락")
        }
        let trimmedText = refinedText.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmedText.isEmpty {
            throw RefineError.emptyResult
        }
        let changes = (dictionary["changes"] as? [Any])?.compactMap { $0 as? String } ?? []
        return RefineResult(refinedText: trimmedText, changes: changes)
    }

    static func stripFences(_ input: String) -> String {
        var text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.hasPrefix("```") {
            if let newline = text.firstIndex(of: "\n") {
                text = String(text[text.index(after: newline)...])
            }
            if text.hasSuffix("```") {
                text = String(text.dropLast(3))
            }
        }
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

public final class GeminiClient: RefiningService {
    private let apiKey: String
    private let model: String
    private let maxRetries: Int
    private let session: URLSession

    public init(apiKey: String, model: String = "gemini-3.6-flash", maxRetries: Int = 2, session: URLSession = .shared) {
        self.apiKey = apiKey
        self.model = model
        self.maxRetries = maxRetries
        self.session = session
    }

    public func refine(_ request: RefineRequest) async throws -> RefineResult {
        try request.validate()
        guard !apiKey.isEmpty else { throw RefineError.missingAPIKey }

        var bodyData: Data {
            let body = APIRequestBody(
                systemInstruction: .init(parts: [.init(text: Prompts.systemPrompt)]),
                contents: [.init(parts: [.init(text: Prompts.buildUserPrompt(request))])],
                generationConfig: .init(responseMimeType: "application/json", temperature: 0.7)
            )
            return (try? JSONEncoder().encode(body)) ?? Data()
        }
        let payload = bodyData

        var lastError: Error = RefineError.apiFailed("unknown")
        for attempt in 0...maxRetries {
            do {
                let responseText = try await sendModelText(payload)
                return try ResultParser.parse(responseText)
            } catch let error as RefineError {
                lastError = error
                if case .parsingFailed = error { throw error }
                if case .emptyResult = error { throw error }
            } catch {
                lastError = RefineError.network(error.localizedDescription)
            }
            if attempt < maxRetries {
                try await Task.sleep(for: .seconds(pow(2, Double(attempt))))
            }
        }
        throw lastError
    }

    struct APIRequestBody: Encodable {
        struct Part: Encodable { let text: String }
        struct Content: Encodable { let parts: [Part] }
        struct SystemInstruction: Encodable { let parts: [Part] }
        struct GenerationConfig: Encodable {
            let responseMimeType: String
            let temperature: Double
        }
        let systemInstruction: SystemInstruction
        let contents: [Content]
        let generationConfig: GenerationConfig
    }

    struct GenerateContentResponse: Decodable {
        struct Candidate: Decodable {
            struct Content: Decodable {
                struct Part: Decodable { let text: String? }
                let parts: [Part]?
            }
            let content: Content?
        }
        struct ErrorBody: Decodable {
            let code: Int?
            let message: String?
            let status: String?
        }
        let candidates: [Candidate]?
        let error: ErrorBody?
    }

    private func sendModelText(_ payload: Data) async throws -> String {
        var request = URLRequest(url: URL(string: "https://generativelanguage.googleapis.com/v1beta/models/\(model):generateContent")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue(apiKey, forHTTPHeaderField: "x-goog-api-key")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = payload

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw RefineError.network(error.localizedDescription)
        }

        guard let http = response as? HTTPURLResponse else {
            throw RefineError.network("알 수 없는 응답")
        }
        switch http.statusCode {
        case 200..<300:
            break
        case 429:
            throw RefineError.rateLimited
        case 401, 403:
            throw RefineError.unauthorized
        default:
            throw RefineError.apiFailed(Self.serverMessage(from: data) ?? "HTTP \(http.statusCode)")
        }

        let decoded: GenerateContentResponse
        do {
            decoded = try JSONDecoder().decode(GenerateContentResponse.self, from: data)
        } catch {
            throw RefineError.parsingFailed("응답 디코딩 실패")
        }
        if let apiError = decoded.error {
            if apiError.code == 429 || apiError.status == "RESOURCE_EXHAUSTED" {
                throw RefineError.rateLimited
            }
            throw RefineError.apiFailed(apiError.message ?? "알 수 없는 오류")
        }
        let text = decoded.candidates?.first?.content?.parts?.compactMap { $0.text }.joined()
        guard let text, !text.isEmpty else {
            throw RefineError.apiFailed("응답에 텍스트가 없습니다")
        }
        return text
    }

    static func serverMessage(from data: Data) -> String? {
        (try? JSONDecoder().decode(GenerateContentResponse.self, from: data))?.error?.message
    }
}
