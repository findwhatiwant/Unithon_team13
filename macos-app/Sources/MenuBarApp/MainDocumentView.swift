import RefinerCore
import SwiftUI

/// 로그인 여부에 따라 로그인 화면 또는 문서 첨삭·리포트 화면을 보여준다.
struct RootView: View {
    @AppStorage("authUserId") private var userId = ""

    var body: some View {
        if userId.isEmpty {
            LoginView()
        } else {
            MainDocumentView()
        }
    }
}

/// 긴 글(편지·논문·과제·블로그)을 첨삭하고 리포트를 받아보는 메인 윈도우.
struct MainDocumentView: View {
    // index.css 토큰
    private let navy = Color(red: 0x41 / 255, green: 0x45 / 255, blue: 0x6b / 255)
    private let navyDark = Color(red: 0x2c / 255, green: 0x2f / 255, blue: 0x52 / 255)
    private let burgundy = Color(red: 0xb0 / 255, green: 0x5a / 255, blue: 0x5b / 255)
    private let frameBg = Color(red: 236 / 255, green: 234 / 255, blue: 242 / 255)
    private let feedbackBorder = Color(red: 0xc5 / 255, green: 0x8c / 255, blue: 0x8f / 255)
    private let feedbackBg = Color(red: 0xe1 / 255, green: 0xd4 / 255, blue: 0xdc / 255)
    private let feedbackText = Color(red: 190.0 / 255, green: 106.0 / 255, blue: 110.0 / 255)
    private let hairline = Color.black.opacity(0.08)

    enum DocCategory: String, CaseIterable {
        case letter = "편지"
        case paper = "논문"
        case assignment = "과제"
        case blog = "블로그"
    }

    enum TaskKind: Equatable {
        case none
        case polish
        case report
    }

    @State private var category: DocCategory = .letter
    @State private var sourceText = ""
    @State private var task: TaskKind = .none
    @State private var errorMessage: String?

    // 첨삭 결과
    @State private var polishedText: String?
    @State private var polishedChanges: [FlexibleChange] = []
    @State private var copiedPolished = false
    @State private var showingResultOnLeft = false

    // 리포트 결과
    @State private var analysis: MagicNoteClient.MirrorAnalysis?
    @State private var copiedRewriteID: String?

    @FocusState private var editorFocused: Bool
    @State private var showReportModal = false
    @State private var report: MagicNoteClient.Report?
    @State private var reportLoading = false
    @State private var reportError: String?

    private let client = MagicNoteClient()

    var body: some View {
        VStack(spacing: 0) {
            header

            categoryRow

            Divider().overlay(hairline)

            HSplit(alignment: .top, spacing: 16) {
                // ── 왼쪽: 입력 ──
                inputColumn
                    .frame(maxWidth: .infinity)

                Divider().overlay(hairline.opacity(0.6))

                // ── 오른쪽: 결과 ──
                resultColumn
                    .frame(maxWidth: .infinity)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
        }
        .frame(minWidth: 720, idealWidth: 780, minHeight: 560, idealHeight: 640)
        .background(
            ZStack {
                frameBg
                Circle().fill(burgundy.opacity(0.07)).blur(radius: 60).frame(width: 260).position(x: 60, y: 60)
                Circle().fill(navy.opacity(0.08)).blur(radius: 60).frame(width: 300).position(x: 600, y: 480)
            }
            .ignoresSafeArea()
        )
        // 리포트 받기 — 우하단 아이콘 버튼 (콘텐츠 위에 떠 있어야 클릭 가능)
        .overlay(alignment: .bottomTrailing) {
            reportFab
                .padding(.trailing, 24)
                .padding(.bottom, 24)
        }
        // 리포트 3단계 모달 (티저 → 분석 → 교정 제안)
        .overlay {
            if showReportModal {
                ReportModalView(
                    report: report,
                    isLoading: reportLoading,
                    errorMessage: reportError,
                    onLoad: { loadReport() },
                    onClose: {
                        withAnimation(.easeInOut(duration: 0.2)) { showReportModal = false }
                    }
                )
                .transition(.opacity)
            }
        }
    }

    // MARK: - 헤더

    private var header: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 8)
                .fill(LinearGradient(colors: [burgundy, navy], startPoint: .topLeading, endPoint: .bottomTrailing))
                .frame(width: 26, height: 26)
                .overlay(
                    Image(systemName: "sparkles")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Color.white.opacity(0.95))
                )
                .shadow(color: burgundy.opacity(0.35), radius: 3, y: 1)

            Text("Magic Note")
                .font(.pretendard(14, .bold))
                .kerning(-0.15)
                .foregroundStyle(Color.black.opacity(0.82))

            Spacer()

            if let email = AuthStore.currentEmail {
                Text(email)
                    .font(.pretendard(10.5))
                    .foregroundStyle(Color.black.opacity(0.35))
            }

            Button {
                AuthStore.logout()
            } label: {
                Text("로그아웃")
                    .font(.pretendard(10.5, .medium))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Capsule().fill(Color.black.opacity(0.05)))
                    .foregroundStyle(Color.black.opacity(0.45))
            }
            .buttonStyle(PressableButtonStyle())
        }
        .padding(.horizontal, 24)
        .padding(.top, 18)
        .padding(.bottom, 12)
    }

    // MARK: - 카테고리 칩

    private var categoryRow: some View {
        HStack(spacing: 8) {
            ForEach(DocCategory.allCases, id: \.self) { item in
                let isActive = category == item
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) { category = item }
                } label: {
                    Text(item.rawValue)
                        .font(.pretendard(12, isActive ? .semibold : .regular))
                        .frame(width: 72)
                        .padding(.vertical, 7)
                        .background(
                            RoundedRectangle(cornerRadius: 999)
                                .fill(isActive ? navy : Color.white.opacity(0.55))
                        )
                        .overlay(
                            Capsule().stroke(isActive ? Color.clear : Color.black.opacity(0.08))
                        )
                        .foregroundStyle(isActive ? Color.white : Color.black.opacity(0.45))
                }
                .buttonStyle(PressableButtonStyle())
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .padding(.bottom, 14)
    }

    // MARK: - 왼쪽: 입력 컬럼

    @ViewBuilder
    private var inputColumn: some View {
        if showingResultOnLeft {
            leftResultColumn
        } else {
            editorColumn
        }
    }

    /// "결과 보기" 누른 뒤 — 왼쪽에 최종 결과 표시
    private var leftResultColumn: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                sectionLabel("다듬은 결과 (")
                Text(category.rawValue)
                    .font(.pretendard(11, .semibold))
                    .foregroundStyle(navy)
                sectionLabel(")")
                Spacer()
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { showingResultOnLeft = false }
                } label: {
                    Label("원본 보기", systemImage: "arrow.left.arrow.right")
                        .font(.pretendard(10.5, .medium))
                        .foregroundStyle(Color.black.opacity(0.4))
                }
                .buttonStyle(.plain)
            }
            .padding(.top, 0)

            ScrollView {
                underlinedPolished(polishedText ?? "")
                    .font(.pretendard(13))
                    .lineSpacing(6)
                    .textSelection(.enabled)
                    .foregroundStyle(Color.black.opacity(0.78))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(14)
            .frame(minHeight: 320, maxHeight: .infinity, alignment: .topLeading)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.75)))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(hairline))

            Button {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(polishedText ?? "", forType: .string)
                copiedPolished = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) { copiedPolished = false }
            } label: {
                Text(copiedPolished ? "복사 완료 ✓" : "복사하기")
                    .font(.pretendard(13, .semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 10)
                            .fill(
                                LinearGradient(
                                    colors: copiedPolished ? [burgundy, Color(red: 0x8f/255, green: 0x45/255, blue: 0x47/255)] : [navy, navyDark],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                    )
                    .foregroundStyle(Color.white)
            }
            .buttonStyle(PressableButtonStyle())
        }
    }

    /// 교정된 부분(corrected 스니펫)을 결과 텍스트에서 찾아 빨간 밑줄을 친다.
    private func underlinedPolished(_ text: String) -> Text {
        guard !polishedChanges.isEmpty else { return Text(text) }

        var ranges: [Range<String.Index>] = []
        var searchStart = text.startIndex
        for change in polishedChanges {
            guard let snippet = change.locator, !snippet.isEmpty else { continue }
            guard let range = text.range(of: snippet, range: searchStart..<text.endIndex)
                ?? text.range(of: snippet) else { continue }
            ranges.append(range)
            searchStart = range.upperBound
        }
        guard !ranges.isEmpty else { return Text(text) }

        ranges.sort { $0.lowerBound < $1.lowerBound }
        var merged: [Range<String.Index>] = []
        for range in ranges {
            if let last = merged.last, range.lowerBound <= last.upperBound {
                merged[merged.count - 1] =
                    Swift.min(last.lowerBound, range.lowerBound)..<Swift.max(last.upperBound, range.upperBound)
            } else {
                merged.append(range)
            }
        }

        var result = Text("")
        var cursor = text.startIndex
        let underlineColor = burgundy.opacity(0.6)
        for range in merged {
            if cursor < range.lowerBound {
                result = result + Text(text[cursor..<range.lowerBound])
            }
            result = result + Text(text[range.lowerBound..<range.upperBound])
                .underline(true, color: underlineColor)
            cursor = range.upperBound
        }
        if cursor < text.endIndex {
            result = result + Text(text[cursor...])
        }
        return result
    }

    private var editorColumn: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionLabel("\(category.rawValue) 원본")

            ZStack(alignment: .topLeading) {
                TextEditor(text: $sourceText)
                    .focused($editorFocused)
                    .font(.pretendard(13))
                    .scrollContentBackground(.hidden)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 6)

                if sourceText.isEmpty && !editorFocused {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(category.rawValue) 글을 붙여넣어 보세요")
                            .font(.pretendard(13, .semibold))
                            .foregroundStyle(Color.black.opacity(0.35))
                        Text(categoryPlaceholder)
                            .font(.pretendard(11.5))
                            .foregroundStyle(Color.black.opacity(0.28))
                    }
                    .padding(.top, 14)
                    .padding(.leading, 13)
                    .allowsHitTesting(false)
                }
            }
            .frame(minHeight: 320, maxHeight: .infinity)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.75)))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(editorFocused ? navy.opacity(0.45) : hairline, lineWidth: editorFocused ? 1.5 : 1)
            )
            .animation(.easeInOut(duration: 0.15), value: editorFocused)

            Button {
                runPolish()
            } label: {
                HStack(spacing: 6) {
                    if task == .polish {
                        ProgressView().controlSize(.small).tint(.white)
                    } else {
                        Image(systemName: "wand.and.stars").font(.system(size: 11, weight: .medium))
                    }
                    Text("다듬기")
                        .font(.pretendard(13, .semibold))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(LinearGradient(colors: [navy, navyDark], startPoint: .topLeading, endPoint: .bottomTrailing))
                        .opacity(canRun ? 1 : 0.4)
                )
                .foregroundStyle(Color.white)
            }
            .buttonStyle(PressableButtonStyle())
            .disabled(!canRun || task != .none)
        }
    }

    private var categoryPlaceholder: String {
        switch category {
        case .letter: return "받는 사람에게 전하는 마음이 담긴 편지를 검토해 드려요"
        case .paper: return "학술적 표현과 논리 구조를 점검해 드려요"
        case .assignment: return "과제 제출 전 문장과 구성을 다듬어 드려요"
        case .blog: return "읽기 좋은 흐름과 어투로 다듬어 드려요"
        }
    }

    /// 카테고리별 첨삭 가이드 — /api/refine의 context로 전달된다.
    private var categoryPromptGuide: String {
        switch category {
        case .letter:
            """
            [첨삭 대상] 받는 사람에게 직접 전하는 개인 편지
            [첨삭 기준]
            - 따뜻하고 진심 어린 어조를 유지하며, 격식 있는 문어체로 바꾸지 않는다.
            - 맞춤법·띄어쓰기·오타를 교정하고, 뜻이 통하지 않는 문장만 매끄럽게 고친다.
            - 인사말·도입·본문·끝맺음의 편지 구조가 자연스러운지 확인하고 비어 있으면 제안한다.
            - 원문의 반말/존댓말 선택과 호칭은 절대 바꾸지 않는다.
            """
        case .paper:
            """
            [첨삭 대상] 학술 논문·학술지 게재용 글
            [첨삭 기준]
            - '~이다', '~하였다' 등 학술적 개조식 문체를 유지한다. 구어체·감정적 표현은 객관적 표현으로 고친다.
            - 전문 용어는 일관되게 유지하고, 임의로 동의어로 바꾸지 않는다. 영문 용어·약자 표기(예: LLM)도 원칙적으로 유지한다.
            - 주장→근거→결론의 논리 흐름에서 연결이 끊기거나 근거 없는 단정이 있으면 지적한다.
            - 수치, 인용, 참고문헌 표기, 통계 수치는 절대 변경하지 않는다.
            """
        case .assignment:
            """
            [첨삭 대상] 학교 과제·레포트·보고서
            [첨삭 기준]
            - 서론→본론→결론의 구조가 드러나도록 문단 구성을 정리한다.
            - 주장과 근거가 섞인 문장은 분리해 명확하게 하고, 두괄식으로 다듬는다.
            - '~것 같다' 같은 불확실한 표현은 과제에 맞게 확신 있는 표현으로 고치되, 사실 관계는 그대로 둔다.
            - 항목 나열은 번호나 불릿으로 정리해 읽기 쉽게 한다.
            """
        case .blog:
            """
            [첨삭 대상] 블로그 포스트
            [첨삭 기준]
            - 독자와 말하는 친근하고 부드러운 어투를 살리되, 과한 의성어·이모티콘 남용은 정리한다. 이모지는 원문 것만 유지한다.
            - 스크롤을 멈추게 하는 소제목과 짧은 문단으로 구조화한다.
            - 도입부(후킹 문장), 본문 경험담, 마무리(요약·독자 행동 유도)의 흐름이 자연스러운지 점검한다.
            - SEO를 위해 핵심 키워드가 자연스럽게 반복되도록 다듬되, 억지 삽입은 하지 않는다.
            """
        }
    }

    // MARK: - 오른쪽: 결과 컬럼

    @ViewBuilder
    private var resultColumn: some View {
        resultsScroll
    }

    private func loadReport() {
        guard let userId = AuthStore.currentUserId else { return }
        reportLoading = true
        reportError = nil
        Task {
            do {
                let result = try await client.fetchReport(userId: userId)
                await MainActor.run {
                    self.report = result
                    self.reportLoading = false
                }
            } catch {
                await MainActor.run {
                    self.reportError = error.localizedDescription
                    self.reportLoading = false
                }
            }
        }
    }

    private var resultsScroll: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if task == .none && polishedText == nil && analysis == nil && errorMessage == nil {
                    emptyResult
                }

                if task == .polish {
                    LoadingRowView(label: "글을 다듬고 있어요...", color: navy)
                }
                if task == .report {
                    LoadingRowView(label: "전달 리포트를 분석 중이에요...", color: burgundy)
                }

                if let errorMessage {
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.circle").font(.system(size: 11))
                        Text(errorMessage)
                    }
                    .font(.pretendard(11))
                    .foregroundStyle(Color.red.opacity(0.75))
                }

                if showingResultOnLeft, polishedText != nil {
                    correctionReportCard()
                } else if let polishedText {
                    polishedCard(polishedText)
                }

                if let analysis {
                    reportCards(analysis)
                }
            }
        }
        .frame(minHeight: 380, maxHeight: .infinity)
    }

    private var emptyResult: some View {
        VStack(spacing: 10) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 26))
                .foregroundStyle(hairline)
            Text("왼쪽에 \(category.rawValue)를 붙여넣고\n다듬기를 눌러보세요")
                .font(.pretendard(12))
                .foregroundStyle(Color.black.opacity(0.35))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 130)
    }

    // MARK: - 리포트 FAB (우하단)

    private var reportFab: some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) { showReportModal = true }
        } label: {
            Group {
                if task == .report {
                    ProgressView()
                        .controlSize(.small)
                        .tint(.white)
                } else {
                    Image(systemName: "chart.bar.doc.horizontal")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundStyle(Color.white)
                }
            }
            .frame(width: 52, height: 52)
            .background(
                Circle()
                    .fill(LinearGradient(colors: [burgundy, Color(red: 0x8f/255, green: 0x45/255, blue: 0x47/255)], startPoint: .topLeading, endPoint: .bottomTrailing))
            )
            .shadow(color: burgundy.opacity(canRun ? 0.45 : 0), radius: 8, y: 3)
        }
        .buttonStyle(PressableButtonStyle(scale: 0.92))
        .disabled(task != .none)
        .help("말투·전달 리포트 받기")
    }

    private var canRun: Bool {
        !sourceText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    // MARK: - 첨삭 결과 카드

    /// 오른쪽: 첨삭 결과 요약 카드 — "결과 보기"로 상세 리포트 전환
    private func polishedCard(_ text: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("다듬은 결과")

            Text(text)
                .font(.pretendard(13))
                .lineSpacing(5)
                .textSelection(.enabled)
                .foregroundStyle(Color.black.opacity(0.72))
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.75)))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(hairline))

            if !polishedChanges.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(Array(polishedChanges.prefix(3).enumerated()), id: \.offset) { _, change in
                        HStack(alignment: .top, spacing: 5) {
                            Circle().fill(burgundy.opacity(0.55)).frame(width: 3, height: 3).padding(.top, 5)
                            Text(change.displayText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .font(.pretendard(10.5))
                .foregroundStyle(Color.black.opacity(0.45))
            }

            HStack(spacing: 8) {
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { showingResultOnLeft = true }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "doc.text.magnifyingglass").font(.system(size: 11, weight: .medium))
                        Text("결과 보기")
                            .font(.pretendard(13, .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 10)
                            .fill(LinearGradient(colors: [navy, navyDark], startPoint: .topLeading, endPoint: .bottomTrailing))
                    )
                    .foregroundStyle(Color.white)
                }
                .buttonStyle(PressableButtonStyle())

                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                    copiedPolished = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) { copiedPolished = false }
                } label: {
                    Image(systemName: copiedPolished ? "checkmark" : "doc.on.doc")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(copiedPolished ? burgundy : Color.black.opacity(0.4))
                        .frame(width: 40)
                        .frame(maxHeight: .infinity)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color.black.opacity(0.05)))
                }
                .buttonStyle(PressableButtonStyle())
            }
            .frame(height: 38)
        }
        .cardBox(hairline: hairline)
    }

    /// 오른쪽: "결과 보기" 이후 — 틀린 부분과 근거 목록
    private func correctionReportCard() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionLabel("교정 리포트 · 틀린 부분과 근거")
                Spacer()
                Text("\(polishedChanges.count)개 항목")
                    .font(.pretendard(10, .semibold))
                    .foregroundStyle(burgundy)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(burgundy.opacity(0.08)))
            }

            if polishedChanges.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "checkmark.seal")
                        .font(.system(size: 22))
                        .foregroundStyle(navy.opacity(0.4))
                    Text("발견된 오류가 없어요\n맞춤법과 문장이 깨끗합니다")
                        .font(.pretendard(12))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(Color.black.opacity(0.4))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
                        } else {
                VStack(spacing: 8) {
                    ForEach(Array(polishedChanges.enumerated()), id: \.offset) { index, change in
                        correctionItem(index: index + 1, change: change)
                    }
                }
            }
        }
        .cardBox(hairline: hairline)
    }

    private func correctionItem(index: Int, change: FlexibleChange) -> some View {
        let issue = change.displayText
        let reason = change.reason ?? ""

        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text("\(index)")
                    .font(.pretendard(9.5, .bold))
                    .foregroundStyle(Color.white)
                    .frame(width: 16, height: 16)
                    .background(Circle().fill(burgundy))

                Text(issue)
                    .font(.pretendard(12, .semibold))
                    .foregroundStyle(Color.black.opacity(0.75))
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !reason.isEmpty {
                HStack(alignment: .top, spacing: 5) {
                    Text("근거")
                        .font(.pretendard(9.5, .semibold))
                        .foregroundStyle(navy)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1)
                        .background(RoundedRectangle(cornerRadius: 4).fill(navy.opacity(0.08)))
                    Text(reason)
                        .font(.pretendard(11))
                        .foregroundStyle(Color.black.opacity(0.55))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.leading, 22)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.6)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(hairline))
    }

    // MARK: - 리포트 카드들

    private func reportCards(_ analysis: MagicNoteClient.MirrorAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.circle").font(.system(size: 10))
                        Text("이렇게 읽힐 수 있어요").font(.pretendard(10, .semibold))
                    }
                    .foregroundStyle(feedbackText)

                    Text("\(analysis.perceivedTone) · \(analysis.intentSummary)")
                        .font(.pretendard(12.5))
                        .lineSpacing(4)
                        .foregroundStyle(feedbackText)
                }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 12).fill(feedbackBg))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(feedbackBorder))

                VStack(alignment: .leading, spacing: 6) {
                    sectionLabel("분석 상태")
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 6) {
                        statusTag("위험도: \(analysis.riskLevel)", warn: analysis.riskLevel != "낮음")
                        statusTag("톤 주의", warn: analysis.riskLevel == "높음")
                        statusTag("의도 보존 ✓", warn: false)
                        statusTag("개선점 \(analysis.riskReasons.count)개", warn: !analysis.riskReasons.isEmpty)
                    }
                }
            }

            if !analysis.riskReasons.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(analysis.riskReasons, id: \.self) { reason in
                        HStack(alignment: .top, spacing: 5) {
                            Circle().fill(feedbackText.opacity(0.6)).frame(width: 3, height: 3).padding(.top, 5)
                            Text(reason)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .font(.pretendard(10.5))
                .foregroundStyle(Color.black.opacity(0.45))
            }

            sectionLabel("추천 교정 문장")

            rewriteCard(id: "soft", badge: "부드럽게", text: analysis.softRewrite)
            rewriteCard(id: "clear", badge: "명확하게", text: analysis.clearRewrite)
            rewriteCard(id: "short", badge: "짧게", text: analysis.shortRewrite)
        }
        .cardBox(hairline: hairline)
    }

    private func statusTag(_ label: String, warn: Bool) -> some View {
        Text(label)
            .font(.pretendard(10.5, .semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 7)
            .background(RoundedRectangle(cornerRadius: 8).fill(warn ? feedbackBg : Color.white.opacity(0.65)))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(warn ? feedbackBorder : Color.black.opacity(0.08), lineWidth: warn ? 1.5 : 1))
            .foregroundStyle(warn ? feedbackText : Color.black.opacity(0.55))
    }

    private func rewriteCard(id: String, badge: String, text: String) -> some View {
        let copied = copiedRewriteID == id
        return VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text(badge)
                    .font(.pretendard(10, .semibold))
                    .foregroundStyle(navy)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(RoundedRectangle(cornerRadius: 5).fill(navy.opacity(0.1)))
                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(navy.opacity(0.18)))

                Spacer()

                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                    copiedRewriteID = id
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.4) { copiedRewriteID = nil }
                } label: {
                    Image(systemName: copied ? "checkmark" : "doc.on.doc")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundStyle(copied ? navy : Color.black.opacity(0.35))
                        .frame(width: 22, height: 22)
                        .background(RoundedRectangle(cornerRadius: 6).fill(navy.opacity(copied ? 0.1 : 0.05)))
                }
                .buttonStyle(PressableButtonStyle())
            }

            Text(text)
                .font(.pretendard(12))
                .lineSpacing(4)
                .textSelection(.enabled)
                .foregroundStyle(Color.black.opacity(0.7))
        }
        .padding(.horizontal, 11)
        .padding(.top, 10)
        .padding(.bottom, 9)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.6)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(hairline))
    }

    private func copyButton(title: String, isCopied: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.pretendard(13, .semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(
                            LinearGradient(
                                colors: isCopied ? [burgundy, Color(red: 0x8f/255, green: 0x45/255, blue: 0x47/255)] : [navy, navyDark],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                )
                .foregroundStyle(Color.white)
        }
        .buttonStyle(PressableButtonStyle())
    }

    // MARK: - 실행

    private func runPolish() {
        let text = sourceText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        task = .polish
        errorMessage = nil

        Task {
            do {
                var request = URLRequest(url: apiBaseURL.appendingPathComponent("api/refine"))
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.timeoutInterval = 180
                var body: [String: Any] = [
                    "text": text,
                    "mode": "polish",
                    // 동의한 경우에만 원문·결과를 서버에 저장한다
                    "save_history": ConsentStore.saveMessageHistory,
                    // 카테고리별 첨삭 가이드를 맥락으로 전달
                    "context": categoryPromptGuide,
                ]
                body["user_id"] = AuthStore.currentUserId
                request.httpBody = try JSONSerialization.data(withJSONObject: body)

                let (data, response) = try await URLSession.shared.data(for: request)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    throw MagicNoteError.server("첨삭 요청 실패")
                }
                struct Response: Decodable {
                    let refinedText: String
                    let changes: [FlexibleChange]
                    enum CodingKeys: String, CodingKey {
                        case refinedText = "refined_text"
                        case changes
                    }
                }
                let decoded = try JSONDecoder().decode(Response.self, from: data)
                await MainActor.run {
                    polishedText = decoded.refinedText
                    polishedChanges = decoded.changes
                    task = .none
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    task = .none
                }
            }
        }
    }

    private func runReport() {
        let text = sourceText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        task = .report
        errorMessage = nil

        Task {
            do {
                let result = try await client.mirror(
                    userId: AuthStore.currentUserId,
                    sessionId: nil,
                    candidateId: nil,
                    text: text,
                    recipient: nil,
                    context: category.rawValue,
                    purpose: category.rawValue,
                    tone: nil
                )
                await MainActor.run {
                    analysis = result
                    task = .none
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    task = .none
                }
            }
        }
    }

    private var apiBaseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "apiBaseURL")
        return URL(string: stored ?? "") ?? URL(string: "http://127.0.0.1:8000")!
    }
}

// MARK: - 공용 프리미티브

private func sectionLabel(_ text: String) -> some View {
    Text(text)
        .font(.pretendard(11, .semibold))
        .tracking(0.45)
        .foregroundStyle(Color.black.opacity(0.35))
}

private struct LoadingRowView: View {
    let label: String
    let color: Color
    @State private var spinning = false

    var body: some View {
        HStack(spacing: 9) {
            Circle()
                .trim(from: 0.15, to: 1)
                .stroke(color, lineWidth: 2)
                .frame(width: 15, height: 15)
                .rotationEffect(.degrees(spinning ? 360 : 0))
                .animation(.linear(duration: 0.7).repeatForever(autoreverses: false), value: spinning)
                .onAppear { spinning = true }

            Text(label)
                .font(.pretendard(12, .semibold))
                .foregroundStyle(Color.black.opacity(0.45))

            Spacer(minLength: 0)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.68)))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.black.opacity(0.08)))
    }
}

private struct HSplit<Content: View>: View {
    let alignment: VerticalAlignment
    let spacing: CGFloat
    @ViewBuilder var content: Content

    init(alignment: VerticalAlignment, spacing: CGFloat, @ViewBuilder content: () -> Content) {
        self.alignment = alignment
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        HStack(alignment: alignment, spacing: spacing) { content }
    }
}

private extension View {
    func cardBox(hairline: Color) -> some View {
        self
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.68)))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(hairline))
            .shadow(color: Color.black.opacity(0.06), radius: 5, y: 2)
    }
}

// MARK: - 흐르는 칩 태그 (말투 습관)

struct FlowChips: View {
    let labels: [String]
    let accent: Color
    let hairline: Color

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 6)], alignment: .leading, spacing: 6) {
            ForEach(labels, id: \.self) { label in
                Text(label)
                    .font(.pretendard(10.5, .medium))
                    .padding(.horizontal, 9)
                    .padding(.vertical, 5)
                    .background(Capsule().fill(accent.opacity(0.07)))
                    .overlay(Capsule().stroke(hairline))
                    .foregroundStyle(Color.black.opacity(0.6))
            }
        }
    }
}
