import RefinerCore
import SwiftUI

struct PopoverView: View {
    @StateObject private var viewModel: RefineViewModel
    @State private var screen: Screen = .home
    @State private var quickText = ""
    @FocusState private var quickFocused: Bool

    enum Screen {
        case home
        case refine
    }

    // Magic Note 팔레트 (HomeScreen 기준)
    private let ink = Color.black.opacity(0.85)
    private let subText = Color.black.opacity(0.45)
    private let surface = Color(white: 0.98)
    private let hairline = Color.black.opacity(0.08)
    private let accent = Color(red: 0x41 / 255, green: 0x45 / 255, blue: 0x6b / 255)   // #41456b
    private let rose = Color(red: 0xb0 / 255, green: 0x5a / 255, blue: 0x5b / 255)     // #b05a5b

    @MainActor
    init(viewModel: RefineViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }

    var body: some View {
        Group {
            switch screen {
            case .home:
                HomeScreenView(
                    quickText: $quickText,
                    quickFocused: $quickFocused,
                    viewModel: viewModel,
                    palette: .init(accent: accent, rose: rose, ink: ink, subText: subText, hairline: hairline),
                    onNavigateInput: { navigateToRefine() },
                    onSend: { navigateToRefine() }
                )
            case .refine:
                RefineScreenView(viewModel: viewModel, palette: .init(accent: accent, rose: rose, ink: ink, subText: subText, hairline: hairline)) {
                    withAnimation(.easeInOut(duration: 0.15)) { screen = .home }
                }
            }
        }
        .frame(width: 340, height: 480)
        .background(Color.white)
    }

    private func navigateToRefine() {
        if !quickText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            viewModel.input = quickText
            quickText = ""
        }
        withAnimation(.easeInOut(duration: 0.15)) { screen = .refine }
    }
}

// MARK: - 팔레트 공유

private struct Palette {
    let accent: Color
    let rose: Color
    let ink: Color
    let subText: Color
    let hairline: Color
}

// MARK: - 홈 화면 (HomeScreen.tsx와 동일한 구조)

private struct HomeScreenView: View {
    @Binding var quickText: String
    var quickFocused: FocusState<Bool>.Binding
    @ObservedObject var viewModel: RefineViewModel
    let palette: Palette
    let onNavigateInput: () -> Void
    let onSend: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            header

            Divider()
                .overlay(palette.hairline)

            hero

            Divider()
                .overlay(palette.hairline)

            footer
        }
    }

    // ── header ──────────────────────────────────────────

    private var header: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 8)
                .fill(
                    LinearGradient(
                        colors: [palette.rose, palette.accent],
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
                .shadow(color: palette.rose.opacity(0.35), radius: 3, y: 1)

            Text("Magic Note")
                .font(.pretendard(14, .bold))
                .kerning(-0.15)
                .foregroundStyle(Color.black.opacity(0.82))

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 10)
    }

    // ── hero ────────────────────────────────────────────

    private var hero: some View {
        VStack(spacing: 26) {
            Text("지금 메세지는 어떤 상태인가요?")
                .font(.pretendard(18, .semibold))
                .kerning(-0.2)
                .foregroundStyle(Color.black.opacity(0.85))
                .multilineTextAlignment(.center)

            Button(action: onNavigateInput) {
                Text("막혔어요")
                    .font(.pretendard(13, .semibold))
                    .padding(.horizontal, 22)
                    .padding(.vertical, 7)
                    .background(Color.white.opacity(0.55))
                    .overlay(Capsule().strokeBorder(palette.rose.opacity(0.35), lineWidth: 1.5))
                    .foregroundStyle(palette.rose)
                    .clipShape(Capsule())
            }
            .buttonStyle(PressableButtonStyle(scale: 0.95))

            inputRow
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.horizontal, 20)
        .padding(.top, 40)
    }

    private var inputRow: some View {
        HStack(spacing: 8) {
            TextField("", text: $quickText)
                .focused(quickFocused)
                .textFieldStyle(.plain)
                .font(.pretendard(12.5))
                .foregroundStyle(Color.black.opacity(0.75))
                .onSubmit(onSend)

            if !viewModel.hasAPIKey {
                Button("키 입력", action: onNavigateInput)
                    .font(.pretendard(11))
                    .buttonStyle(.plain)
                    .foregroundStyle(palette.subText)
            }

            Button(action: onSend) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.white)
                    .frame(width: 30, height: 30)
                    .background(
                        Circle().fill(
                            LinearGradient(
                                colors: [palette.accent, Color(red: 0x2c/255, green: 0x2f/255, blue: 0x52/255)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .opacity(canSend ? 1 : 0.4)
                    )
                    .shadow(color: canSend ? palette.accent.opacity(0.4) : .clear, radius: 4, y: 1)
            }
            .buttonStyle(PressableButtonStyle(scale: 0.92))
            .disabled(!canSend)
        }
        .padding(6)
        .padding(.leading, 10)
        .background(Color.white.opacity(0.6))
        .overlay(Capsule().stroke(Color.black.opacity(0.08)))
        .clipShape(Capsule())
        .shadow(color: Color.black.opacity(0.05), radius: 1, y: 1)
    }

    private var canSend: Bool {
        !quickText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && viewModel.hasAPIKey
    }

    // ── footer ──────────────────────────────────────────

    private var footer: some View {
        HStack {
            footerButton(icon: "gearshape", action: onNavigateInput)

            Spacer()

            Text("Magic Note · Unithon Team13")
                .font(.pretendard(10))
                .foregroundStyle(palette.subText)
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

// MARK: - 다듬기 화면 (기존 기능 유지)

private struct RefineScreenView: View {
    private let surface = Color(white: 0.98)

    @ObservedObject var viewModel: RefineViewModel
    @FocusState private var toneFocused: Bool
    @FocusState private var inputFocused: Bool
    let palette: Palette
    let onBack: () -> Void

    @State private var showContext = false
    @State private var apiKeyInput = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Button(action: onBack) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(Color.black.opacity(0.5))
                        .frame(width: 26, height: 26)
                        .background(RoundedRectangle(cornerRadius: 7).fill(Color.black.opacity(0.05)))
                }
                .buttonStyle(PressableButtonStyle())

                Text("다듬기")
                    .font(.pretendard(14, .bold))
                    .foregroundStyle(Color.black.opacity(0.82))

                Spacer()
            }
            .padding(.top, 14)

            Divider().overlay(palette.hairline)

            if !viewModel.hasAPIKey {
                apiKeySection
            }

            styleSection

            if viewModel.mode == .tone {
                HStack(spacing: 6) {
                    ForEach(Tone.allCases) { tone in
                        categoryButton(title: tone.label, isSelected: viewModel.tone == tone) {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                viewModel.tone = viewModel.tone == tone ? nil : tone
                            }
                        }
                    }
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            if showContext || !viewModel.contextInput.isEmpty {
                TextField("상황·받는 사람 (선택)", text: $viewModel.contextInput)
                    .focused($toneFocused)
                    .textFieldStyle(.plain)
                    .font(.pretendard(11))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(surface, in: RoundedRectangle(cornerRadius: 9))
                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(palette.hairline))
            } else {
                Button {
                    withAnimation { showContext = true }
                } label: {
                    Label("상황 추가", systemImage: "plus.circle")
                        .font(.pretendard(11))
                        .foregroundStyle(palette.subText)
                }
                .buttonStyle(.plain)
            }

            editor

            errorMessageArea

            resultCard

            Spacer(minLength: 0)

            footer
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 10)
    }

    // MARK: 입력

    private var editor: some View {
        ZStack(alignment: .topLeading) {
            HStack(alignment: .bottom, spacing: 6) {
                ZStack(alignment: .topLeading) {
                    TextEditor(text: $viewModel.input)
                        .focused($inputFocused)
                        .font(.pretendard(12.5))
                        .scrollContentBackground(.hidden)
                        .frame(height: 64)
                        .padding(.top, 6)
                        .padding(.leading, 4)

                    if viewModel.input.isEmpty && !inputFocused {
                        Text("작성 중이던 초안이나 답장을 입력해 보세요")
                            .font(.pretendard(12.5))
                            .foregroundStyle(Color.black.opacity(0.32))
                            .padding(.top, 12)
                            .padding(.leading, 9)
                            .allowsHitTesting(false)
                    }
                }

                Button {
                    Task { await viewModel.refine() }
                } label: {
                    Group {
                        if viewModel.isLoading {
                            ProgressView()
                                .controlSize(.mini)
                                .tint(.white)
                        } else {
                            Image(systemName: "arrow.up")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(Color.white)
                        }
                    }
                    .frame(width: 30, height: 30)
                    .background(
                        Circle().fill(
                            LinearGradient(
                                colors: [palette.accent, Color(red: 0x2c/255, green: 0x2f/255, blue: 0x52/255)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .opacity(canRefine ? 1 : 0.4)
                    )
                    .shadow(color: canRefine ? palette.accent.opacity(0.4) : .clear, radius: 4, y: 1)
                }
                .buttonStyle(PressableButtonStyle(scale: 0.92))
                .disabled(!canRefine)
                .keyboardShortcut(.return, modifiers: .command)
                .padding(.bottom, 4)
                .padding(.trailing, 5)
            }
        }
        .background(RoundedRectangle(cornerRadius: 22).fill(Color.white.opacity(0.6)))
        .overlay(
            RoundedRectangle(cornerRadius: 22)
                .stroke(inputFocused ? palette.accent.opacity(0.45) : palette.hairline, lineWidth: inputFocused ? 1.5 : 1)
        )
        .animation(.easeInOut(duration: 0.15), value: inputFocused)
    }

    private var canRefine: Bool {
        !viewModel.isLoading
            && !viewModel.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && viewModel.hasAPIKey
    }

    // MARK: 스타일

    private var styleSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("무엇을 도와드릴까요?")
                .font(.pretendard(11, .semibold))
                .tracking(0.3)
                .foregroundStyle(palette.subText)

            HStack(spacing: 6) {
                ForEach(Mode.allCases) { mode in
                    categoryButton(title: mode.label, isSelected: viewModel.mode == mode) {
                        withAnimation(.easeInOut(duration: 0.15)) { viewModel.mode = mode }
                    }
                }
            }
        }
    }

    private func categoryButton(title: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.pretendard(12, isSelected ? .semibold : .regular))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 7)
                .background(Capsule().fill(isSelected ? palette.accent : Color.black.opacity(0.04)))
                .foregroundStyle(isSelected ? Color.white : palette.ink)
                .overlay(Capsule().stroke(isSelected ? Color.clear : palette.hairline))
        }
        .buttonStyle(PressableButtonStyle(scale: 0.96))
    }

    // MARK: 에러

    @ViewBuilder
    private var errorMessageArea: some View {
        if let errorMessage = viewModel.errorMessage {
            HStack(alignment: .top, spacing: 6) {
                Image(systemName: "exclamationmark.circle").font(.system(size: 11))
                Text(errorMessage).fixedSize(horizontal: false, vertical: true)
            }
            .foregroundColor(Color(red: 0.80, green: 0.25, blue: 0.20))
            .font(.pretendard(11))
            .transition(.opacity)
        }
    }

    // MARK: 결과

    private var resultCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("결과")
                    .font(.pretendard(11, .semibold))
                    .tracking(0.3)
                    .foregroundStyle(palette.subText)
                Spacer()
                if let result = viewModel.result {
                    Button {
                        viewModel.copyResult()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: viewModel.copied ? "checkmark" : "doc.on.doc")
                                .font(.system(size: 9, weight: .medium))
                            Text(viewModel.copied ? "복사됨" : "복사")
                                .font(.pretendard(11, .medium))
                        }
                        .foregroundStyle(viewModel.copied ? Color.green : palette.accent)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(
                            Capsule().fill(viewModel.copied ? Color.green.opacity(0.08) : palette.accent.opacity(0.07))
                        )
                    }
                    .buttonStyle(PressableButtonStyle())
                    .disabled(viewModel.copied)
                }
            }

            if let result = viewModel.result {
                ScrollView {
                    Text(result.refinedText)
                        .textSelection(.enabled)
                        .font(.pretendard(13))
                        .foregroundStyle(palette.ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 120)
                .padding(10)
                .background(surface, in: RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(palette.hairline))

                Group {
                    if result.changes.isEmpty {
                        Text("")
                    } else {
                        VStack(alignment: .leading, spacing: 3) {
                            ForEach(result.changes, id: \.self) { change in
                                HStack(alignment: .top, spacing: 5) {
                                    Circle()
                                        .fill(palette.rose.opacity(0.55))
                                        .frame(width: 3, height: 3)
                                        .padding(.top, 5)
                                    Text(change)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                }
                .font(.pretendard(10.5))
                .foregroundStyle(palette.subText)
                .frame(height: 40, alignment: .top)
                .clipped()
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: 14).fill(surface)
                    VStack(spacing: 6) {
                        Image(systemName: "text.bubble")
                            .font(.system(size: 16))
                            .foregroundStyle(palette.hairline)
                        Text(viewModel.isLoading ? "다듬는 중..." : "결과가 여기에 표시됩니다")
                            .font(.pretendard(11))
                            .foregroundStyle(palette.subText)
                    }
                }
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(palette.hairline, style: StrokeStyle(lineWidth: 1, dash: [4]))
                )
                .frame(height: 120)
            }
        }
    }

    // MARK: API 키

    private var apiKeySection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label {
                Text("Gemini API 키를 입력하세요")
                    .font(.pretendard(12, .medium))
            } icon: {
                Image(systemName: "key").font(.system(size: 10))
            }
            .foregroundStyle(palette.ink)

            HStack(spacing: 8) {
                SecureField("API 키", text: $apiKeyInput)
                    .textFieldStyle(.plain)
                    .font(.pretendard(12))

                Button {
                    viewModel.apiKeyInput = apiKeyInput
                    viewModel.saveAPIKey()
                } label: {
                    Text("저장")
                        .font(.pretendard(12, .semibold))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(RoundedRectangle(cornerRadius: 7).fill(palette.accent))
                        .foregroundStyle(Color.white)
                }
                .buttonStyle(PressableButtonStyle())
                .disabled(apiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(palette.hairline))
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.orange.opacity(0.06)))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.orange.opacity(0.25)))
    }

    // MARK: 푸터

    private var footer: some View {
        HStack(spacing: 10) {
            Button {
                NSApp.terminate(nil)
            } label: {
                Image(systemName: "power")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(Color.black.opacity(0.4))
                    .frame(width: 26, height: 26)
                    .background(RoundedRectangle(cornerRadius: 7).fill(Color.black.opacity(0.05)))
            }
            .buttonStyle(PressableButtonStyle())

            Spacer()

            Text("Magic Note · Unithon Team13")
                .font(.pretendard(10))
                .foregroundStyle(palette.subText)
        }
        .padding(.top, 6)
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
