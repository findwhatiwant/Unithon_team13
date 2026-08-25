import Foundation

/// 로그인 상태면 FastAPI 서버(/api/refine)를 경유해 말투 프로필이 반영된 결과를 받고,
/// 아니면 Gemini를 직접 호출한다.
public struct APIRefineService: RefiningService {
    public init() {}

    public func refine(_ request: RefineRequest) async throws -> RefineResult {
        if let userId = AuthStore.currentUserId {
            return try await refineViaAPI(request, userId: userId)
        }
        return try await GeminiClient(apiKey: APIKeyStore.savedKey ?? "").refine(request)
    }

    private func refineViaAPI(_ request: RefineRequest, userId: String) async throws -> RefineResult {
        var body: [String: Any] = [
            "user_id": userId,
            "text": request.text,
            "mode": request.mode.rawValue,
            "save_history": ConsentStore.saveMessageHistory, // 동의한 경우에만 원문 저장 (말투 학습 재료)
        ]
        body["tone"] = request.tone?.rawValue
        body["context"] = request.context

        var urlRequest = URLRequest(url: baseURL.appendingPathComponent("api/refine"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.timeoutInterval = 30
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        guard let http = response as? HTTPURLResponse else {
            throw RefineError.network("알 수 없는 응답")
        }

        switch http.statusCode {
        case 200..<300:
            break
        case 429:
            throw RefineError.rateLimited
        case 401:
            throw RefineError.unauthorized
        default:
            // 서버 오류 시 직접 Gemini 호출로 폴백
            return try await GeminiClient(apiKey: APIKeyStore.savedKey ?? "").refine(request)
        }

        struct APIResponse: Decodable {
            let refinedText: String
            let changes: [FlexibleChange]

            enum CodingKeys: String, CodingKey {
                case refinedText = "refined_text"
                case changes
            }
        }
        do {
            let decoded = try JSONDecoder().decode(APIResponse.self, from: data)
            return RefineResult(
                refinedText: decoded.refinedText,
                changes: decoded.changes.map(\.displayText)
            )
        } catch {
            throw RefineError.parsingFailed("서버 응답 형식 오류")
        }
    }

    private var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "apiBaseURL")
        return URL(string: stored ?? "") ?? URL(string: "http://127.0.0.1:8000")!
    }
}
