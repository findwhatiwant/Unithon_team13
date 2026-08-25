import AppKit
import Foundation
import Combine
import RefinerCore

/// Magic Note 피드 스트림 상태 머신 (App.tsx의 Step과 1:1 대응)
@MainActor
public final class ChatViewModel: ObservableObject {
    public enum Step: Equatable {
        case idle
        case drafting
        case drafts
        case analyzing
        case analyzed
        case rewriting
        case done
    }

    public enum Mode: String {
        case review   // 검토·분석 (mirror)
        case blocked  // 막혔어요 — 초안 생성 (compose)
    }

    public static let purposes = ["사과", "거절", "요청", "피드백"]
    public static let toneStyles = ["정중하게", "부드럽게", "친근하게", "아련하게"]

    @Published public var step: Step = .idle
    @Published public var mode: Mode = .review
    @Published public var purpose: String = "요청"
    @Published public var inputValue = ""
    @Published public var sentText = ""
    @Published public var errorMessage: String?

    // 홈 화면 컨텍스트 (상대방/본인/어투)
    @Published public var counterpart = ""
    @Published public var selfDescription = ""
    @Published public var toneStyle: String?

    // 초안 카드 상태
    @Published public var sessionId: String?
    @Published public var drafts: [MagicNoteClient.Candidate] = []
    @Published public var selectedDraftIdx = 0
    @Published public var draftCopiedIdx: Int?
    @Published public var copiedDraftId: String?

    // 분석/최종 상태
    @Published public var analysis: MagicNoteClient.MirrorAnalysis?
    @Published public var finalCopied = false

    private let client = MagicNoteClient()

    public init() {}

    public var isComposerLocked: Bool { step != .idle }

    /// 대화를 모두 지우고 처음 화면(idle)으로 되돌린다.
    public func resetToInitial() {
        step = .idle
        mode = .review
        purpose = "요청"
        inputValue = ""
        sentText = ""
        errorMessage = nil
        sessionId = nil
        drafts = []
        selectedDraftIdx = 0
        draftCopiedIdx = nil
        copiedDraftId = nil
        analysis = nil
        finalCopied = false
    }

    /// 분석 상태 태그 (AnalysisCard의 STATUS_TAGS)
    public var statusTags: [(label: String, warn: Bool)] {
        guard let analysis else { return [] }
        let toneWarn = analysis.riskLevel != "낮음"
        return [
            ("의도 보존 ✓", false),
            ("톤 주의", toneWarn),
            ("구조 ✓", false),
            ("위험 단어 \(analysis.riskReasons.count)개", analysis.riskReasons.isEmpty ? false : true),
        ]
    }

    public func toggleMode() {
        mode = mode == .review ? .blocked : .review
    }

    public func send() {
        let text = inputValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, step == .idle else { return }
        sentText = text
        inputValue = ""
        errorMessage = nil

        switch mode {
        case .blocked:
            step = .drafting
            Task { await runCompose(context: composedContext(text)) }
        case .review:
            step = .analyzing
            Task { await runMirror(text: text, sessionId: nil, candidateId: nil) }
        }
    }

    /// 상대방/본인/어투 정보를 문맥 문자열로 합성 (프롬프트에 전달)
    private func composedContext(_ text: String) -> String {
        var parts: [String] = []
        if !counterpart.isEmpty { parts.append("받는 사람: \(counterpart)") }
        if !selfDescription.isEmpty { parts.append("보내는 사람: \(selfDescription)") }
        if let toneStyle { parts.append("원하는 어투: \(toneStyle)") }
        parts.append("상황: \(text)")
        return parts.joined(separator: " / ")
    }

    public func copyDraft(_ draft: MagicNoteClient.Candidate) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(draft.text, forType: .string)
        draftCopiedIdx = drafts.firstIndex(where: { $0.id == draft.id })
        Task {
            try? await Task.sleep(nanoseconds: 1_400_000_000)
            await MainActor.run { self.draftCopiedIdx = nil }
        }
    }

    /// 선택한 초안으로 미러 분석 진행
    public func confirmDraft() {
        guard drafts.indices.contains(selectedDraftIdx) else { return }
        let draft = drafts[selectedDraftIdx]
        step = .analyzing
        Task {
            await runMirror(
                text: draft.text,
                sessionId: sessionId,
                candidateId: draft.id
            )
        }
    }

    /// 분석 확인 → 최종 교정 화면
    public func confirmAnalysis() {
        guard let analysis else { return }
        step = .rewriting
        Task {
            try? await Task.sleep(nanoseconds: 900_000_000)
            await MainActor.run {
                self.analysis = analysis
                self.step = .done
            }
        }
    }

    public var finalText: String? {
        analysis?.softRewrite
    }

    public func copyFinal() {
        guard let finalText else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(finalText, forType: .string)
        finalCopied = true
        Task {
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            await MainActor.run { self.finalCopied = false }
        }
    }

    // MARK: - 백엔드 호출

    private func runCompose(context: String) async {
        do {
            let result = try await client.compose(
                userId: AuthStore.currentUserId,
                context: context,
                purpose: purpose,
                tone: nil
            )
            sessionId = result.sessionId
            drafts = result.candidates
            selectedDraftIdx = min(1, max(0, result.candidates.count - 1))
            step = .drafts
        } catch {
            fail(error)
        }
    }

    private func runMirror(text: String, sessionId: String?, candidateId: String?) async {
        do {
            analysis = try await client.mirror(
                userId: AuthStore.currentUserId,
                sessionId: sessionId,
                candidateId: candidateId,
                text: text,
                recipient: counterpart.isEmpty ? nil : counterpart,
                context: mode == .blocked ? composedContext(sentText) : composedContext(text),
                purpose: mode == .blocked ? purpose : nil,
                tone: nil
            )
            step = .analyzed
        } catch {
            fail(error)
        }
    }

    private func fail(_ error: Error) {
        if let magicError = error as? MagicNoteError {
            errorMessage = magicError.errorDescription
        } else {
            errorMessage = error.localizedDescription
        }
        step = .idle
    }
}
