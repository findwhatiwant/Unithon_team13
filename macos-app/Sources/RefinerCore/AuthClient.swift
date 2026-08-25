import Foundation

public struct AuthResponse: Codable {
    public let userId: String
    public let email: String?
    public let nickname: String?
    public let accessToken: String
    public let refreshToken: String?

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case email
        case nickname
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
    }
}

public struct AuthError: Error, LocalizedError {
    public let message: String

    public var errorDescription: String? { message }

    init(status: Int, body: Data?) {
        if let body,
           let decoded = try? JSONDecoder().decode(APIErrorBody.self, from: body),
           let detail = decoded.detail {
            message = Self.friendlyMessage(detail)
        } else if status == 400 {
            message = "이미 가입된 이메일이거나 형식이 올바르지 않습니다."
        } else if status == 401 {
            message = "이메일 또는 비밀번호가 올바르지 않습니다."
        } else {
            message = "서버에 연결할 수 없습니다. (\(status))"
        }
    }

    private static func friendlyMessage(_ raw: String) -> String {
        if raw.contains("already registered") || raw.contains("already been registered") {
            return "이미 가입된 이메일입니다."
        }
        if raw.contains("Password should be") {
            return "비밀번호는 8자 이상이어야 합니다."
        }
        if raw.contains("Invalid login") || raw.contains("invalid") {
            return "이메일 또는 비밀번호가 올바르지 않습니다."
        }
        return raw
    }
}

private struct APIErrorBody: Decodable {
    let detail: String?
}

public enum AuthStore {
    private static let userKey = "authUserId"
    private static let emailKey = "authEmail"
    private static let tokenKey = "authAccessToken"

    public static var isLoggedIn: Bool {
        UserDefaults.standard.string(forKey: userKey)?.isEmpty == false
    }

    public static var currentUserId: String? {
        UserDefaults.standard.string(forKey: userKey)
    }

    public static var currentEmail: String? {
        UserDefaults.standard.string(forKey: emailKey)
    }

    public static func saveSession(_ response: AuthResponse) {
        UserDefaults.standard.set(response.userId, forKey: userKey)
        UserDefaults.standard.set(response.email, forKey: emailKey)
        UserDefaults.standard.set(response.accessToken, forKey: tokenKey)
    }

    public static func logout() {
        UserDefaults.standard.removeObject(forKey: userKey)
        UserDefaults.standard.removeObject(forKey: emailKey)
        UserDefaults.standard.removeObject(forKey: tokenKey)
    }
}

public struct AuthClient {
    public init() {}

    /// FastAPI 서버 주소 (기본: 로컬 개발 서버)
    public var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "apiBaseURL")
        return URL(string: stored ?? "") ?? URL(string: "http://127.0.0.1:8000")!
    }

    public func signUp(email: String, password: String, nickname: String?) async throws -> AuthResponse {
        var body: [String: Any] = ["email": email, "password": password]
        if let nickname, !nickname.isEmpty { body["nickname"] = nickname }
        return try await request(path: "api/auth/signup", body: body, fallbackStatuses: [400])
    }

    public func logIn(email: String, password: String) async throws -> AuthResponse {
        try await request(
            path: "api/auth/login",
            body: ["email": email, "password": password],
            fallbackStatuses: [401]
        )
    }

    public struct Consents {
        public var messageHistory: Bool
        public var coachAnalysis: Bool
        public var sensitiveInfo: Bool

        public init(messageHistory: Bool = false, coachAnalysis: Bool = false, sensitiveInfo: Bool = false) {
            self.messageHistory = messageHistory
            self.coachAnalysis = coachAnalysis
            self.sensitiveInfo = sensitiveInfo
        }
    }

    public func saveConsents(userId: String, consents: Consents) async throws {
        var urlRequest = URLRequest(url: baseURL.appendingPathComponent("api/consents"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.timeoutInterval = 15
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: [
            "user_id": userId,
            "save_message_history": consents.messageHistory,
            "coach_analysis": consents.coachAnalysis,
            "sensitive_info_storage": consents.sensitiveInfo,
        ])
        let (_, response) = try await URLSession.shared.data(for: urlRequest)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw AuthError(status: (response as? HTTPURLResponse)?.statusCode ?? -1, body: nil)
        }
    }

    private func request(
        path: String,
        body: [String: Any],
        fallbackStatuses: [Int]
    ) async throws -> AuthResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw AuthError(status: -1, body: nil)
        }
        guard (200..<300).contains(http.statusCode) else {
            throw AuthError(status: http.statusCode, body: data)
        }
        do {
            return try JSONDecoder().decode(AuthResponse.self, from: data)
        } catch {
            throw AuthError(status: 500, body: data)
        }
    }
}
