import AppKit
import Foundation
import Combine

@MainActor
public final class RefineViewModel: ObservableObject {
    @Published public var input = ""
    @Published public var contextInput = ""
    @Published public var mode: Mode = .polish
    @Published public var tone: Tone? {
        didSet { toneChanged() }
    }
    @Published public var isLoading = false
    @Published public var result: RefineResult?
    @Published public var errorMessage: String?
    @Published public var copied = false
    @Published public var hasAPIKey: Bool
    @Published public var apiKeyInput = ""

    private let service: RefiningService

    public init(service: RefiningService? = nil) {
        self.service = service ?? APIRefineService()
        self.hasAPIKey = AuthStore.isLoggedIn || APIKeyStore.savedKey != nil
    }

    public func refine() async {
        errorMessage = nil
        do {
            let request = RefineRequest(
                text: input,
                mode: mode,
                tone: mode == .tone ? (tone ?? .formal) : nil,
                context: contextInput.isEmpty ? nil : contextInput
            )
            try request.validate()
            isLoading = true
            defer { isLoading = false }
            result = try await service.refine(request)
            copied = false
        } catch let error as RefineError {
            errorMessage = error.message
        } catch {
            errorMessage = RefineError.apiFailed(error.localizedDescription).message
        }
    }

    public func copyResult() {
        guard let refinedText = result?.refinedText else { return }
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(refinedText, forType: .string)
        copied = true
    }

    public func saveAPIKey() {
        let key = apiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { return }
        APIKeyStore.save(key)
        hasAPIKey = true
        apiKeyInput = ""
    }

    private func toneChanged() {
        if mode == .tone && tone == nil {
            tone = .formal
        }
    }
}
