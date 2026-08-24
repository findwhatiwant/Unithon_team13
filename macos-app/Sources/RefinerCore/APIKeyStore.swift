import Foundation

public enum APIKeyStore {
    private static let defaultsKey = "geminiApiKey"

    public static var savedKey: String? {
        if let key = UserDefaults.standard.string(forKey: defaultsKey), !key.isEmpty {
            return key
        }
        if let key = ProcessInfo.processInfo.environment["GEMINI_API_KEY"], !key.isEmpty {
            return key
        }
        return nil
    }

    public static func save(_ key: String) {
        UserDefaults.standard.set(key, forKey: defaultsKey)
    }
}
