import Foundation

public enum APIKeyStore {
    private static let defaultsKey = "geminiApiKey"
    private static let secretsPlistName = "Secrets"

    /// 베타 기간 동안 앱에 내장된 기본 키 (빌드 시점에 .env에서 주입되며 소스에는 없음)
    private static var embeddedKey: String? {
        guard let url = Bundle.main.url(forResource: secretsPlistName, withExtension: "plist"),
              let data = try? Data(contentsOf: url),
              let secrets = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any],
              let key = secrets["GEMINI_API_KEY"] as? String
        else { return nil }
        return key.isEmpty ? nil : key
    }

    public static var savedKey: String? {
        if let key = UserDefaults.standard.string(forKey: defaultsKey), !key.isEmpty {
            return key
        }
        if let key = ProcessInfo.processInfo.environment["GEMINI_API_KEY"], !key.isEmpty {
            return key
        }
        return embeddedKey
    }

    public static func save(_ key: String) {
        UserDefaults.standard.set(key, forKey: defaultsKey)
    }
}
