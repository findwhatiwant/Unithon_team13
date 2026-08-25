import RefinerCore
import SwiftUI

/// Magic Note 피드 스트림 UI — App.tsx / index.css와 1:1 대응
struct PopoverView: View {
    @StateObject private var chat = ChatViewModel()

    // index.css 토큰
    private let navy = Color(red: 0x41 / 255, green: 0x45 / 255, blue: 0x6b / 255)        // #41456b
    private let navyDark = Color(red: 0x2c / 255, green: 0x2f / 255, blue: 0x52 / 255)    // #2c2f52
    private let burgundy = Color(red: 0xb0 / 255, green: 0x5a / 255, blue: 0x5b / 255)    // #b05a5b
    private let frameBg = Color(red: 236 / 255, green: 234 / 255, blue: 242 / 255)        // #eceaf2
    private let feedbackBorder = Color(red: 0xc5 / 255, green: 0x8c / 255, blue: 0x8f / 255)
    private let feedbackBg = Color(red: 0xe1 / 255, green: 0xd4 / 255, blue: 0xdc / 255)
    private let feedbackText = Color(red: 190.0 / 255, green: 106.0 / 255, blue: 110.0 / 255)

    var body: some View {
        VStack(spacing: 0) {
            feedHeader

            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if chat.step == .idle {
                        emptyState
                    } else {
                        feedList
                        Color.clear.frame(height: 1)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 12)
            }

            feedFooter
        }
        .frame(width: 360, height: 520)
        .background(
            // app-frame-glow: 은은한 방사형 그라데이션
            ZStack {
                frameBg
                LinearGradient(
                    colors: [
                        Color.clear,
                        Color.clear,
                    ],
                    startPoint: .top, endPoint: .bottom
                )
            }
            .overlay(
                GeometryReader { _ in
                    ZStack {
                        Circle()
                            .fill(burgundy.opacity(0.08))
                            .blur(radius: 40)
                            .frame(width: 220, height: 220)
                            .position(x: 60, y: 50)
                        Circle()
                            .fill(navy.opacity(0.09))
                            .blur(radius: 40)
                            .frame(width: 240, height: 240)
                            .position(x: 300, y: 470)
                    }
                }
            )
            .ignoresSafeArea()
        )
    }

    // MARK: - 헤더 (feed-header + home-logo + home-title)

    private var feedHeader: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 8)
                .fill(
                    LinearGradient(
                        colors: [burgundy, navy],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
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

            // 맨처음으로 돌아가기 — 진행 중인 피드를 지우고 초기 화면으로
            if chat.step != .idle {
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        chat.resetToInitial()
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.counterclockwise")
                            .font(.system(size: 9, weight: .medium))
                        Text("처음으로")
                            .font(.pretendard(10.5, .medium))
                    }
                    .foregroundStyle(Color.black.opacity(0.45))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Capsule().fill(Color.black.opacity(0.05)))
                }
                .buttonStyle(PressableButtonStyle())
                .help("대화를 지우고 처음 화면으로 돌아갑니다")
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 10)
    }

    // MARK: - 빈 상태 (중앙 입력 폼)

    private var emptyState: some View {
        VStack(spacing: 18) {
            Text("지금 메세지는 어떤 상태인가요?")
                .font(.pretendard(17, .semibold))
                .kerning(-0.2)
                .foregroundStyle(Color.black.opacity(0.85))
                .multilineTextAlignment(.center)

            contextRow

            centerInputRow

            Text("막혔나요?")
                .font(.pretendard(11.5))
                .foregroundStyle(Color.black.opacity(0.32))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.horizontal, 20)
    }

    /// 상대방 · 본인 · 어투 한 줄
    private var contextRow: some View {
        HStack(spacing: 6) {
            HStack(spacing: 4) {
                Image(systemName: "person")
                    .font(.system(size: 9))
                    .foregroundStyle(Color.black.opacity(0.3))
                TextField("상대방", text: $chat.counterpart)
                    .textFieldStyle(.plain)
                    .font(.pretendard(11.5))
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(Color.white.opacity(0.6))
            .overlay(Capsule().stroke(Color.black.opacity(0.08)))
            .clipShape(Capsule())

            HStack(spacing: 4) {
                Image(systemName: "person.fill")
                    .font(.system(size: 9))
                    .foregroundStyle(Color.black.opacity(0.3))
                TextField("본인", text: $chat.selfDescription)
                    .textFieldStyle(.plain)
                    .font(.pretendard(11.5))
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(Color.white.opacity(0.6))
            .overlay(Capsule().stroke(Color.black.opacity(0.08)))
            .clipShape(Capsule())

            Menu {
                ForEach(ChatViewModel.toneStyles, id: \.self) { style in
                    Button(style) {
                        chat.toneStyle = chat.toneStyle == style ? nil : style
                    }
                }
                if chat.toneStyle != nil {
                    Button("선택 없음") {
                        chat.toneStyle = nil
                    }
                }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "quote.opening")
                        .font(.system(size: 9))
                        .foregroundStyle(chat.toneStyle == nil ? Color.black.opacity(0.3) : navy)
                    Text(chat.toneStyle ?? "어투")
                        .font(.pretendard(11.5, chat.toneStyle == nil ? .regular : .semibold))
                        .lineLimit(1)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 7, weight: .semibold))
                        .foregroundStyle(Color.black.opacity(0.3))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(
                    Capsule().fill(chat.toneStyle == nil ? Color.white.opacity(0.6) : navy.opacity(0.08))
                )
                .overlay(
                    Capsule().stroke(chat.toneStyle == nil ? Color.black.opacity(0.08) : navy.opacity(0.35))
                )
                .foregroundStyle(chat.toneStyle == nil ? Color.black.opacity(0.45) : navy)
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
        }
    }

    /// 중앙 캡슐 입력창 + 전송 버튼
    private var centerInputRow: some View {
        HStack(spacing: 8) {
            TextField("", text: $chat.inputValue)
                .textFieldStyle(.plain)
                .font(.pretendard(13))
                .foregroundStyle(Color.black.opacity(0.75))
                .placeholder(when: chat.inputValue.isEmpty) {
                    Text("작성 중이던 초안이나 답장을 입력해 보세요")
                        .font(.pretendard(12.5))
                        .foregroundStyle(Color.black.opacity(0.32))
                        .allowsHitTesting(false)
                }
                .onSubmit { chat.send() }

            Button {
                chat.send()
            } label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.white)
                    .frame(width: 30, height: 30)
                    .background(
                        Circle()
                            .fill(LinearGradient(colors: [navy, navyDark], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .opacity(canSend ? 1 : 0.4)
                    )
                    .shadow(color: canSend ? navy.opacity(0.4) : .clear, radius: 4, y: 1)
            }
            .buttonStyle(PressableButtonStyle(scale: 0.92))
            .disabled(!canSend)
        }
        .padding(6)
        .padding(.leading, 14)
        .background(Color.white.opacity(0.6))
        .overlay(Capsule().stroke(Color.black.opacity(0.08)))
        .clipShape(Capsule())
        .shadow(color: Color.black.opacity(0.05), radius: 1, y: 1)
        .frame(maxWidth: 300)
    }

    private var canSend: Bool {
        !chat.inputValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    // MARK: - 피드 목록 (feed-list)

    @ViewBuilder
    private var feedList: some View {
        if chat.step != .idle {
            UserBubble(text: chat.sentText)

            switch chat.step {
            case .drafting:
                LoadingRow(label: "상황에 맞는 초안 \(3)개를 생성 중이에요...", spinnerColor: navy)
            case .drafts:
                DraftListCard(
                    drafts: chat.drafts,
                    selectedIdx: $chat.selectedDraftIdx,
                    copiedIdx: chat.draftCopiedIdx,
                    onSelect: { chat.selectedDraftIdx = $0 },
                    onCopy: { chat.copyDraft($0) },
                    onConfirm: { chat.confirmDraft() },
                    navy: navy,
                    hairline: Color.black.opacity(0.08)
                )
            case .analyzing:
                LoadingRow(label: "상대방에게 어떻게 전달될지 분석 중이에요...", spinnerColor: navy)
            case .analyzed, .rewriting, .done:
                AnalysisCard(
                    analysis: chat.analysis,
                    statusTags: chat.statusTags,
                    onConfirm: { chat.confirmAnalysis() },
                    navy: navy,
                    feedbackBorder: feedbackBorder,
                    feedbackBg: feedbackBg,
                    feedbackText: feedbackText
                )
                if chat.step == .rewriting {
                    LoadingRow(label: "문장을 교정 중이에요...", spinnerColor: navy)
                }
                if chat.step == .done, let finalText = chat.finalText {
                    FinalCard(
                        text: finalText,
                        copied: $chat.finalCopied,
                        onCopy: { chat.copyFinal() },
                        navy: navy,
                        burgundy: burgundy,
                        navyDark: navyDark
                    )
                }
            default:
                EmptyView()
            }

            if let errorMessage = chat.errorMessage {
                Text(errorMessage)
                    .font(.pretendard(11))
                    .foregroundStyle(Color.red.opacity(0.75))
            }
        }
    }

    // MARK: - 푸터 (막혔어요·입력창은 홈 중앙 폼으로 이동)

    private var feedFooter: some View {
        HStack {
            footerButton(icon: "gearshape", action: {})
            Spacer()
            Text("Magic Note · Unithon Team13")
                .font(.pretendard(10))
                .foregroundStyle(Color.black.opacity(0.45))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    private func footerButton(icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(Color.black.opacity(0.4))
                .frame(width: 26, height: 26)
                .background(RoundedRectangle(cornerRadius: 7).fill(Color.black.opacity(0.05)))
        }
        .buttonStyle(PressableButtonStyle())
    }
}

// MARK: - 피드 아이템들

private struct UserBubble: View {
    let text: String

    var body: some View {
        HStack {
            Spacer()
            Text(text)
                .font(.pretendard(12.5))
                .lineSpacing(5)
                .foregroundStyle(Color.white)
                .padding(.horizontal, 13)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(LinearGradient(colors: [Color(red: 0x41/255, green: 0x45/255, blue: 0x6b/255), Color(red: 0x2c/255, green: 0x2f/255, blue: 0x52/255)], startPoint: .topLeading, endPoint: .bottomTrailing))
                )
                .shadow(color: Color(red: 0x41/255, green: 0x45/255, blue: 0x6b/255).opacity(0.3), radius: 5, y: 2)
                .frame(maxWidth: 280, alignment: .trailing)
        }
    }
}

private struct LoadingRow: View {
    let label: String
    let spinnerColor: Color
    @State private var spinning = false

    var body: some View {
        HStack(spacing: 9) {
            Circle()
                .trim(from: 0.15, to: 1)
                .stroke(spinnerColor, lineWidth: 2)
                .frame(width: 15, height: 15)
                .rotationEffect(.degrees(spinning ? 360 : 0))
                .animation(.linear(duration: 0.7).repeatForever(autoreverses: false), value: spinning)

            Text(label)
                .font(.pretendard(12, .semibold))
                .foregroundStyle(Color.black.opacity(0.45))
                .modifier(ShimmerEffect())

            Spacer(minLength: 0)
        }
        .onAppear { spinning = true }
    }
}

private struct ShimmerEffect: ViewModifier {
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    LinearGradient(
                        colors: [.clear, Color.white.opacity(0.9), .clear],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geo.size.width * 0.6)
                    .offset(x: phase * geo.size.width * 1.6)
                }
                .blendMode(.screen)
            )
            .mask(content)
            .onAppear {
                withAnimation(.linear(duration: 1.6).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }
}

private struct DraftListCard: View {
    let drafts: [MagicNoteClient.Candidate]
    @Binding var selectedIdx: Int
    let copiedIdx: Int?
    let onSelect: (Int) -> Void
    let onCopy: (MagicNoteClient.Candidate) -> Void
    let onConfirm: () -> Void
    let navy: Color
    let hairline: Color

    private let versions = ["기본형", "부드럽게", "명확하게"]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("추천 초안 \(drafts.count)가지")

            VStack(spacing: 8) {
                ForEach(Array(drafts.enumerated()), id: \.element.id) { index, draft in
                    draftCard(index: index, draft: draft)
                }
            }

            primaryButton(title: "선택하고 Mirror로 확인", action: onConfirm, fillColor: navy, gradientTo: Color(red: 0x2c/255, green: 0x2f/255, blue: 0x52/255))
        }
        .cardStyle(hairline: hairline)
    }

    private func draftCard(index: Int, draft: MagicNoteClient.Candidate) -> some View {
        let isSelected = selectedIdx == index
        return Button {
            onSelect(index)
        } label: {
            VStack(alignment: .leading, spacing: 7) {
                HStack {
                    Text(draft.index <= versions.count ? versions[draft.index - 1] : "후보 \(draft.index)")
                        .font(.pretendard(10, .semibold))
                        .foregroundStyle(navy)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(RoundedRectangle(cornerRadius: 5).fill(navy.opacity(0.1)))
                        .overlay(RoundedRectangle(cornerRadius: 5).stroke(navy.opacity(0.18)))

                    Spacer()

                    Button {
                        onCopy(draft)
                    } label: {
                        Image(systemName: copiedIdx == index ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundStyle(copiedIdx == index ? navy : Color.black.opacity(0.35))
                            .frame(width: 22, height: 22)
                            .background(RoundedRectangle(cornerRadius: 6).fill(navy.opacity(copiedIdx == index ? 0.1 : 0.05)))
                    }
                    .buttonStyle(PressableButtonStyle())
                }

                Text(draft.text)
                    .font(.pretendard(12))
                    .lineSpacing(4)
                    .foregroundStyle(Color.black.opacity(0.7))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 11)
            .padding(.top, 10)
            .padding(.bottom, 9)
            .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(isSelected ? 0.95 : 0.6)))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? navy.opacity(0.4) : hairline, lineWidth: isSelected ? 1.5 : 1)
            )
        }
        .buttonStyle(.plain)
    }
}

private struct AnalysisCard: View {
    let analysis: MagicNoteClient.MirrorAnalysis?
    let statusTags: [(label: String, warn: Bool)]
    let onConfirm: () -> Void
    let navy: Color
    let feedbackBorder: Color
    let feedbackBg: Color
    let feedbackText: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.circle")
                        .font(.system(size: 10))
                    Text("이렇게 읽힐 수 있어요")
                        .font(.pretendard(10, .semibold))
                }
                .foregroundStyle(feedbackText)

                Text(analysis.map { "\($0.perceivedTone) · \($0.intentSummary)" } ?? "")
                    .font(.pretendard(12))
                    .lineSpacing(4)
                    .foregroundStyle(feedbackText)
            }
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 12).fill(feedbackBg))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(feedbackBorder))

            VStack(alignment: .leading, spacing: 6) {
                sectionLabel("분석 상태")
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 6) {
                    ForEach(statusTags, id: \.label) { tag in
                        Text(tag.label)
                            .font(.pretendard(10.5, .semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 7)
                            .background(
                                RoundedRectangle(cornerRadius: 8).fill(tag.warn ? feedbackBg : Color.white.opacity(0.65))
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 8).stroke(tag.warn ? feedbackBorder : Color.black.opacity(0.08), lineWidth: tag.warn ? 1.5 : 1)
                            )
                            .foregroundStyle(tag.warn ? feedbackText : Color.black.opacity(0.55))
                    }
                }
            }

            primaryButton(title: "교정 문장 확인하기", action: onConfirm, fillColor: navy, gradientTo: Color(red: 0x2c/255, green: 0x2f/255, blue: 0x52/255))
        }
        .cardStyle(hairline: Color.black.opacity(0.08))
    }
}

private struct FinalCard: View {
    let text: String
    @Binding var copied: Bool
    let onCopy: () -> Void
    let navy: Color
    let burgundy: Color
    let navyDark: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel("최종 미리보기")

            Text(text)
                .font(.pretendard(12.5))
                .lineSpacing(5)
                .textSelection(.enabled)
                .foregroundStyle(Color.black.opacity(0.72))
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.75)))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.black.opacity(0.09)))

            Button(action: onCopy) {
                Text(copied ? "복사 완료 ✓" : "복사하기")
                    .font(.pretendard(13, .semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 10)
                            .fill(LinearGradient(colors: copied ? [burgundy, Color(red: 0x8f/255, green: 0x45/255, blue: 0x47/255)] : [navy, navyDark], startPoint: .topLeading, endPoint: .bottomTrailing))
                    )
                    .foregroundStyle(Color.white)
            }
            .buttonStyle(PressableButtonStyle())
        }
        .cardStyle(hairline: Color.black.opacity(0.08))
    }
}

// MARK: - 공용 프리미티브

private func sectionLabel(_ text: String) -> some View {
    Text(text)
        .font(.pretendard(11, .semibold))
        .tracking(0.45)
        .foregroundStyle(Color.black.opacity(0.35))
}

private func primaryButton(title: String, action: @escaping () -> Void, fillColor: Color, gradientTo: Color) -> some View {
    Button(action: action) {
        Text(title)
            .font(.pretendard(13, .semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(LinearGradient(colors: [fillColor, gradientTo], startPoint: .topLeading, endPoint: .bottomTrailing))
            )
            .foregroundStyle(Color.white)
            .shadow(color: fillColor.opacity(0.4), radius: 5, y: 2)
    }
    .buttonStyle(PressableButtonStyle())
}

private struct FrameFill<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private extension View {
    func cardStyle(hairline: Color) -> some View {
        self
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.white.opacity(0.68))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(hairline)
            )
            .shadow(color: Color.black.opacity(0.06), radius: 5, y: 2)
    }

    func placeholder<Content: View>(when shouldShow: Bool, @ViewBuilder placeholder: () -> Content) -> some View {
        ZStack(alignment: .leading) {
            placeholder().opacity(shouldShow ? 1 : 0)
            self
        }
    }
}

// MARK: - 버튼 눌림 효과

struct PressableButtonStyle: ButtonStyle {
    var scale: CGFloat = 0.97

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scale : 1)
            .animation(.easeOut(duration: 0.1), value: configuration.isPressed)
    }
}
