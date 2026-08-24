import RefinerCore
import SwiftUI

struct PopoverView: View {
    @StateObject private var viewModel: RefineViewModel

    @MainActor
    init(viewModel: RefineViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !viewModel.hasAPIKey {
                apiKeySection
            }

            Picker("모드", selection: $viewModel.mode) {
                ForEach(Mode.allCases) { mode in
                    Text(mode.label).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            if viewModel.mode == .tone {
                Picker("톤", selection: $viewModel.tone) {
                    Text("선택").tag(Tone?.none)
                    ForEach(Tone.allCases) { tone in
                        Text(tone.label).tag(Tone?.some(tone))
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
            }

            TextField("상황·받는 사람 (선택)", text: $viewModel.contextInput)
                .textFieldStyle(.roundedBorder)
                .font(.system(size: 12))

            ZStack(alignment: .topLeading) {
                TextEditor(text: $viewModel.input)
                    .font(.system(size: 13))
                    .scrollContentBackground(.hidden)
                    .frame(height: 90)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color.gray.opacity(0.35))
                    )
                if viewModel.input.isEmpty {
                    Text("보낼 메시지를 입력하세요")
                        .foregroundColor(.gray)
                        .font(.system(size: 13))
                        .padding(.top, 8)
                        .padding(.leading, 5)
                        .allowsHitTesting(false)
                }
            }

            HStack {
                Button {
                    Task { await viewModel.refine() }
                } label: {
                    if viewModel.isLoading {
                        ProgressView()
                            .controlSize(.small)
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("다듬기")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(viewModel.isLoading || viewModel.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !viewModel.hasAPIKey)
                .keyboardShortcut(.return, modifiers: .command)

                Spacer(minLength: 0)
            }

            if let errorMessage = viewModel.errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let result = viewModel.result {
                resultSection(result)
            }

            Divider()

            HStack {
                Text("Unithon Team13")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("종료") {
                    NSApp.terminate(nil)
                }
                .font(.caption)
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(width: 340)
    }

    private var apiKeySection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Gemini API 키를 입력하세요 (aistudio.google.com)")
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack {
                SecureField("API 키", text: $viewModel.apiKeyInput)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12))
                Button("저장") {
                    viewModel.saveAPIKey()
                }
                .disabled(viewModel.apiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(8)
        .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
    }

    private func resultSection(_ result: RefineResult) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("결과").font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button(viewModel.copied ? "복사됨" : "클립보드 복사") {
                    viewModel.copyResult()
                }
                .font(.caption)
                .buttonStyle(.bordered)
                .controlSize(.small)
                .disabled(viewModel.copied)
            }

            ScrollView {
                Text(result.refinedText)
                    .textSelection(.enabled)
                    .font(.system(size: 13))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 110)
            .padding(8)
            .background(Color.blue.opacity(0.06), in: RoundedRectangle(cornerRadius: 8))

            if !result.changes.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(result.changes, id: \.self) { change in
                        HStack(alignment: .top, spacing: 4) {
                            Text("•")
                            Text(change).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
            }
        }
    }
}
