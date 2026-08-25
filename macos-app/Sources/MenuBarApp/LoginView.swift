import RefinerCore
import SwiftUI

struct LoginView: View {
    enum Mode {
        case logIn
        case signUp
    }

    @State private var mode: Mode = .logIn
    @State private var email = ""
    @State private var password = ""
    @State private var nickname = ""
    @State private var agreedPrivacy = false
    @State private var consentHistory = false
    @State private var consentSensitive = false
    @State private var errorMessage: String?
    @State private var isLoading = false

    private let client = AuthClient()

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 10) {
                Image(systemName: "wand.and.stars")
                    .font(.system(size: 34))
                    .foregroundStyle(Color.black)

                Text("Magic note")
                    .font(.pretendard(20, .bold))
                    .foregroundStyle(Color.black)

                Text(mode == .logIn ? "계정으로 로그인하세요" : "새 계정을 만드세요")
                    .font(.pretendard(12))
                    .foregroundStyle(.gray)
            }
            .padding(.top, 4)

            Picker("", selection: $mode) {
                Text("로그인").tag(Mode.logIn)
                Text("회원가입").tag(Mode.signUp)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(width: 220)

            VStack(spacing: 10) {
                if mode == .signUp {
                    field(icon: "person", placeholder: "닉네임 (선택)", text: $nickname)
                }
                field(icon: "envelope", placeholder: "이메일", text: $email)
                field(icon: "lock", placeholder: "비밀번호 (8자 이상)", text: $password, isSecure: true)
            }

            if mode == .signUp {
                consentSection
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.pretendard(11))
                    .foregroundStyle(Color(red: 0.80, green: 0.25, blue: 0.20))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Button {
                submit()
            } label: {
                HStack(spacing: 6) {
                    if isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text(mode == .logIn ? "로그인" : "동의하고 가입하기")
                            .font(.pretendard(14, .semibold))
                    }
                }
                .foregroundStyle(Color.white)
                .frame(maxWidth: .infinity)
                .frame(height: 40)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.black)
                        .opacity(canSubmit ? 1 : 0.3)
                )
            }
            .buttonStyle(PressableButtonStyle())
            .disabled(!canSubmit || isLoading)
            .keyboardShortcut(.return)

            Text("메뉴바에서도 언제든 사용할 수 있습니다")
                .font(.pretendard(11))
                .foregroundStyle(.gray)

            Spacer(minLength: 0)
        }
        .padding(32)
        .frame(width: 340, height: 460)
        .background(Color.white)
    }

    private var canSubmit: Bool {
        let base = !email.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !password.isEmpty
        return mode == .logIn ? base : (base && agreedPrivacy)
    }

    // MARK: - 동의 체크란

    private var consentSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            checkRow(
                isChecked: $agreedPrivacy,
                title: "[필수] 개인정보 수집·이용 동의",
                detail: "계정 생성 및 서비스 제공을 위해 이메일, 닉네임을 수집하며, 회원 탈퇴 시 지체 없이 파기합니다."
            )

            Divider()

            checkRow(
                isChecked: $consentHistory,
                title: "[선택] 메시지 저장·말투 학습",
                detail: "다듬은 원본 메시지를 저장해 내 말투에 맞는 결과를 제공합니다. 거부 시 일반 교정만 제공됩니다."
            )

            checkRow(
                isChecked: $consentSensitive,
                title: "[선택] 민감정보 저장",
                detail: "메시지에 포함된 민감한 정보의 저장을 허용합니다. 거부 시 민감정보는 저장하지 않습니다."
            )
        }
        .padding(12)
        .background(Color(white: 0.98), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.black.opacity(0.08)))
    }

    private func checkRow(
        isChecked: Binding<Bool>,
        title: String,
        detail: String
    ) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.15)) { isChecked.wrappedValue.toggle() }
        } label: {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: isChecked.wrappedValue ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 14))
                    .foregroundStyle(isChecked.wrappedValue ? Color(red: 0x41/255, green: 0x45/255, blue: 0x6b/255) : Color.black.opacity(0.25))
                    .padding(.top, 1)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.pretendard(11.5, .semibold))
                        .foregroundStyle(Color.black.opacity(0.8))
                    Text(detail)
                        .font(.pretendard(10))
                        .foregroundStyle(Color.black.opacity(0.4))
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }
        }
        .buttonStyle(.plain)
    }

    private func field(
        icon: String,
        placeholder: String,
        text: Binding<String>,
        isSecure: Bool = false
    ) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(.gray)
                .frame(width: 16)

            Group {
                if isSecure {
                    SecureField(placeholder, text: text)
                } else {
                    TextField(placeholder, text: text)
                }
            }
            .textFieldStyle(.plain)
            .font(.pretendard(13))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Color(white: 0.98), in: RoundedRectangle(cornerRadius: 9))
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Color.black.opacity(0.08)))
    }

    private func submit() {
        errorMessage = nil
        isLoading = true

        Task {
            do {
                let response: AuthResponse
                switch mode {
                case .logIn:
                    response = try await client.logIn(
                        email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                        password: password
                    )
                case .signUp:
                    response = try await client.signUp(
                        email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                        password: password,
                        nickname: nickname.isEmpty ? nil : nickname
                    )
                    // 선택 동의 항목 저장 (실패해도 가입은 유지)
                    try? await client.saveConsents(
                        userId: response.userId,
                        consents: AuthClient.Consents(
                            messageHistory: consentHistory,
                            coachAnalysis: consentHistory,
                            sensitiveInfo: consentSensitive
                        )
                    )
                }
                AuthStore.saveSession(response)
            } catch let error as AuthError {
                errorMessage = error.message
            } catch {
                errorMessage = "서버에 연결할 수 없습니다. 서버 실행 여부를 확인하세요."
            }
            isLoading = false
        }
    }
}
