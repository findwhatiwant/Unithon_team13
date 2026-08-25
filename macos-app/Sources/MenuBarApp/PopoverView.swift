import RefinerCore
import SwiftUI

struct PopoverView: View {
    @StateObject private var viewModel: RefineViewModel
    @FocusState private var inputFocused: Bool

    // 미니멀 화이트 팔레트
    private let ink = Color(red: 0.12, green: 0.13, blue: 0.15)          // 본문 진한 회색
    private let subText = Color(red: 0.55, green: 0.57, blue: 0.60)      // 보조 텍스트
    private let surface = Color(white: 0.98)                             // 입력 카드 배경
    private let hairline = Color.black.opacity(0.08)
    private let accent = Color.black                                     // 포인트 컬러

    @MainActor
    init(viewModel: RefineViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if !viewModel.hasAPIKey {
                apiKeySection
            }

            VStack(alignment: .leading, spacing: 8) {
                sectionTitle("스타일")

                HStack(spacing: 6) {
                    ForEach(Mode.allCases) { mode in
                        categoryButton(
                            title: mode.label,
                            isSelected: viewModel.mode == mode
                        ) {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                viewModel.mode = mode
                            }
                        }
                    }
                }

                if viewModel.mode == .tone {
                    HStack(spacing: 6) {
                        ForEach(Tone.allCases) { tone in
                            categoryButton(
                                title: tone.label,
                                isSelected: viewModel.tone == tone
                            ) {
                                withAnimation(.easeInOut(duration: 0.15)) {
                                    viewModel.tone = viewModel.tone == tone ? nil : tone
                                }
                            }
                        }
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                sectionTitle("메시지")

                TextField("상황·받는 사람 (선택)", text: $viewModel.contextInput)
                    .textFieldStyle(.plain)
                    .font(.pretendard(12))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(surface, in: RoundedRectangle(cornerRadius: 9))
                    .overlay(
                        RoundedRectangle(cornerRadius: 9)
                            .stroke(hairline)
                    )

                ZStack(alignment: .topLeading) {
                    TextEditor(text: $viewModel.input)
                        .focused($inputFocused)
                        .font(.pretendard(13))
                        .scrollContentBackground(.hidden)
                        .frame(height: 90)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 4)
                        .background(surface, in: RoundedRectangle(cornerRadius: 9))
                        .overlay(
                            RoundedRectangle(cornerRadius: 9)
                                .stroke(inputFocused ? Color.black.opacity(0.35) : hairline, lineWidth: inputFocused ? 1.5 : 1)
                        )
                        .animation(.easeInOut(duration: 0.15), value: inputFocused)

                    if viewModel.input.isEmpty {
                        Text("보낼 메시지를 입력하세요")
                            .foregroundColor(subText)
                            .font(.pretendard(13))
                            .padding(.top, 11)
                            .padding(.leading, 11)
                            .allowsHitTesting(false)
                    }
                }
            }

            Button {
                Task { await viewModel.refine() }
            } label: {
                HStack(spacing: 6) {
                    if viewModel.isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Image(systemName: "sparkles")
                            .font(.pretendard(12, .medium))
                        Text("다듬기")
                            .font(.pretendard(14, .semibold))
                    }
                }
                .foregroundStyle(Color.white)
                .frame(maxWidth: .infinity)
                .frame(height: 38)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(accent)
                        .opacity(canRefine ? 1 : 0.3)
                )
            }
            .buttonStyle(PressableButtonStyle())
            .disabled(!canRefine)
            .keyboardShortcut(.return, modifiers: .command)

            ZStack {
                if let errorMessage = viewModel.errorMessage {
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "exclamationmark.circle")
                            .font(.pretendard(11))
                        Text(errorMessage)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .foregroundColor(Color(red: 0.80, green: 0.25, blue: 0.20))
                    .font(.caption)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 24, maxHeight: 24, alignment: .topLeading)

            resultCard

            Spacer(minLength: 0)

            Divider()

            HStack {
                Text("Unithon Team13")
                    .font(.pretendard(10))
                    .foregroundStyle(subText)
                Spacer()
                Button {
                    NSApp.terminate(nil)
                } label: {
                    Text("종료")
                        .font(.pretendard(11))
                        .foregroundStyle(subText)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(18)
        .frame(width: 340, height: 590)
        .background(Color.white)
    }

    private var canRefine: Bool {
        !viewModel.isLoading
            && !viewModel.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && viewModel.hasAPIKey
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.pretendard(11, .semibold))
            .tracking(0.5)
            .textCase(.uppercase)
            .foregroundStyle(subText)
    }

    private func categoryButton(
        title: String,
        isSelected: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            Text(title)
                .font(.pretendard(12, isSelected ? .semibold : .regular))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(isSelected ? accent : Color.black.opacity(0.04))
                )
                .foregroundStyle(isSelected ? Color.white : ink)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(isSelected ? Color.clear : hairline)
                )
        }
        .buttonStyle(PressableButtonStyle(scale: 0.96))
    }

    private var apiKeySection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label {
                Text("Gemini API 키를 입력하세요")
                    .font(.pretendard(12, .medium))
            } icon: {
                Image(systemName: "key")
                    .font(.pretendard(10))
            }
            .foregroundStyle(ink)

            HStack(spacing: 8) {
                SecureField("API 키", text: $viewModel.apiKeyInput)
                    .textFieldStyle(.plain)
                    .font(.pretendard(12))

                Button {
                    viewModel.saveAPIKey()
                } label: {
                    Text("저장")
                        .font(.pretendard(12, .semibold))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 5)
                        .background(RoundedRectangle(cornerRadius: 7).fill(accent))
                        .foregroundStyle(Color.white)
                }
                .buttonStyle(PressableButtonStyle())
                .disabled(viewModel.apiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(hairline))

            Text("[aistudio.google.com/apikey](https://aistudio.google.com/apikey)")
                .font(.pretendard(10))
                .foregroundStyle(subText)
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.orange.opacity(0.06))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.orange.opacity(0.25))
        )
    }

    private var resultCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                sectionTitle("결과")
                Spacer()
                if let result = viewModel.result {
                    Button {
                        viewModel.copyResult()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: viewModel.copied ? "checkmark" : "doc.on.doc")
                                .font(.pretendard(9, .medium))
                            Text(viewModel.copied ? "복사됨" : "복사")
                                .font(.pretendard(11, .medium))
                        }
                        .foregroundStyle(viewModel.copied ? Color.green : ink)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(
                            RoundedRectangle(cornerRadius: 7)
                                .fill(viewModel.copied ? Color.green.opacity(0.08) : Color.black.opacity(0.04))
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
                        .foregroundStyle(ink)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 120)
                .padding(10)
                .background(surface, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(hairline))

                Group {
                    if result.changes.isEmpty {
                        Text("")
                    } else {
                        VStack(alignment: .leading, spacing: 3) {
                            ForEach(result.changes, id: \.self) { change in
                                HStack(alignment: .top, spacing: 5) {
                                    Circle()
                                        .fill(subText.opacity(0.5))
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
                .foregroundStyle(subText)
                .frame(height: 40, alignment: .top)
                .clipped()
            } else {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(surface)
                    VStack(spacing: 6) {
                        Image(systemName: "text.bubble")
                            .font(.pretendard(16))
                            .foregroundStyle(hairline)
                        Text(viewModel.isLoading ? "다듬는 중..." : "결과가 여기에 표시됩니다")
                            .font(.pretendard(11))
                            .foregroundStyle(subText)
                    }
                }
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(hairline, style: StrokeStyle(lineWidth: 1, dash: [4])))
                .frame(height: 120)
            }
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
