import SwiftUI

struct LoginView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        VStack(spacing: 28) {
            VStack(spacing: 10) {
                Image(systemName: "wand.and.stars")
                    .font(.system(size: 34))
                    .foregroundStyle(Color.black)

                Text("메시지 다듬기")
                    .font(.pretendard(20, .bold))
                    .foregroundStyle(Color.black)

                Text("계정으로 로그인하세요")
                    .font(.pretendard(12))
                    .foregroundStyle(.gray)
            }
            .padding(.top, 8)

            VStack(spacing: 10) {
                field(icon: "envelope", placeholder: "이메일", text: $email)

                field(icon: "lock", placeholder: "비밀번호", text: $password, isSecure: true)
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.pretendard(11))
                    .foregroundStyle(Color(red: 0.80, green: 0.25, blue: 0.20))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Button {
                login()
            } label: {
                HStack(spacing: 6) {
                    if isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text("로그인")
                            .font(.pretendard(14, .semibold))
                    }
                }
                .foregroundStyle(Color.white)
                .frame(maxWidth: .infinity)
                .frame(height: 40)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.black)
                        .opacity(canLogin ? 1 : 0.3)
                )
            }
            .buttonStyle(PressableButtonStyle())
            .disabled(!canLogin || isLoading)
            .keyboardShortcut(.return)

            Text("메뉴바에서도 언제든 사용할 수 있습니다")
                .font(.pretendard(11))
                .foregroundStyle(.gray)

            Spacer(minLength: 0)
        }
        .padding(32)
        .frame(width: 340, height: 400)
        .background(Color.white)
    }

    private var canLogin: Bool {
        !email.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !password.isEmpty
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

    private func login() {
        errorMessage = nil
        isLoading = true

        // TODO: 실제 인증 연동 시 교체
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            isLoading = false
            NSApp.hide(nil)
        }
    }
}
