import RefinerCore
import SwiftUI

/// home-design 브랜치의 PlanReportModal을 SwiftUI로 포팅한 3단계 리포트 모달.
///
/// State 1 티저(블러 잠금) → State 2 습관 분석(리스트 + 막대그래프) → State 3 교정 제안(before → after).
struct ReportModalView: View {
    private let navy = Color(red: 0x41 / 255, green: 0x45 / 255, blue: 0x6b / 255)
    private let navyDark = Color(red: 0x2c / 255, green: 0x2f / 255, blue: 0x52 / 255)

    private enum ModalState: Int {
        case teaser, analysis, correction
    }

    private typealias Mistake = (label: String, count: Int, before: String?, after: String?)

    private struct Correction {
        let habit: String
        let description: String?
        let before: String?
        let after: String?
    }

    let report: MagicNoteClient.Report?
    let isLoading: Bool
    let errorMessage: String?
    let onLoad: () -> Void
    let onClose: () -> Void

    @State private var state: ModalState = .teaser
    @State private var spinning = false

    var body: some View {
        ZStack {
            backdrop

            panel
                .frame(maxWidth: 600)
                .frame(minHeight: 380, maxHeight: 560)
                .padding(.horizontal, 32)
                .transition(.opacity.combined(with: .scale(scale: 0.94).combined(with: .offset(y: 8))))
        }
        .onExitCommand { onClose() }
        .onAppear(perform: loadIfNeeded)
    }

    // MARK: - 배경 오버레이

    private var backdrop: some View {
        Color.black.opacity(0.45)
            .background(.ultraThinMaterial)
            .ignoresSafeArea()
            .contentShape(Rectangle())
            .onTapGesture { onClose() }
            .transition(.opacity)
    }

    // MARK: - 모달 패널

    private var panel: some View {
        ZStack(alignment: .topTrailing) {
            RoundedRectangle(cornerRadius: 20)
                .fill(Color.white.opacity(0.97))
                .shadow(color: .black.opacity(0.3), radius: 30, y: 12)
                .shadow(color: .black.opacity(0.12), radius: 6, y: 2)

            content
                .padding(36)
                .padding(.trailing, 26)

            closeButton
                .padding(18)
        }
    }

    private var closeButton: some View {
        Button {
            onClose()
        } label: {
            Image(systemName: "xmark")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(Color.black.opacity(0.5))
                .frame(width: 28, height: 28)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.05)))
        }
        .buttonStyle(PressableButtonStyle())
        .help("닫기")
    }

    @ViewBuilder
    private var content: some View {
        if isLoading {
            loadingContent
        } else if let errorMessage {
            errorContent(errorMessage)
        } else if let report {
            reportContent(report)
        } else {
            emptyContent
        }
    }

    // MARK: - 로딩 / 에러 / 빈 화면

    private var loadingContent: some View {
        VStack(spacing: 14) {
            Circle()
                .trim(from: 0.15, to: 1)
                .stroke(navy, lineWidth: 2.4)
                .frame(width: 24, height: 24)
                .rotationEffect(.degrees(spinning ? 360 : 0))
                .animation(.linear(duration: 0.7).repeatForever(autoreverses: false), value: spinning)
            Text("나의 글 습관을 분석하고 있어요...")
                .font(.pretendard(13, .semibold))
                .foregroundStyle(Color.black.opacity(0.45))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { spinning = true }
    }

    private func errorContent(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.circle")
                .font(.system(size: 22))
                .foregroundStyle(Color.red.opacity(0.65))
            Text(message)
                .font(.pretendard(12))
                .multilineTextAlignment(.center)
                .foregroundStyle(Color.red.opacity(0.75))

            Button {
                onLoad()
            } label: {
                Text("다시 시도")
                    .font(.pretendard(11.5, .semibold))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 7)
                    .background(Capsule().fill(navy.opacity(0.08)))
                    .foregroundStyle(navy)
            }
            .buttonStyle(PressableButtonStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyContent: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.system(size: 24))
                .foregroundStyle(Color.black.opacity(0.15))
            Text("누적된 교정 기록이 아직 없어요.\n메시지를 다듬으면 리포트를 만들 수 있어요.")
                .font(.pretendard(12))
                .multilineTextAlignment(.center)
                .foregroundStyle(Color.black.opacity(0.35))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - State 1 · 유료 플랜 티저

    @ViewBuilder
    private func reportContent(_ report: MagicNoteClient.Report) -> some View {
        switch state {
        case .teaser:
            teaserState(report)
        case .analysis:
            analysisState(report)
        case .correction:
            correctionState(report)
        }
    }

    private func teaserState(_ report: MagicNoteClient.Report) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("지금까지 쓰신 \(report.totalReviews)개의 문장을 분석해서\n무의식적으로 사용하는 습관들을 발견했어요.")
                .font(.pretendard(19, .medium))
                .lineSpacing(6)
                .foregroundStyle(Color.black.opacity(0.82))

            teaserBox
        }
    }

    private var teaserBox: some View {
        ZStack {
            VStack(alignment: .leading, spacing: 12) {
                fakeLine(width: 0.88)
                fakeLine(width: 0.72)
                fakeLine(width: 0.94)
                fakeLine(width: 0.60)
                fakeLine(width: 0.80)
                fakeLine(width: 0.70)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .blur(radius: 5)
            .opacity(0.7)

            LinearGradient(
                colors: [Color.white.opacity(0), Color.white.opacity(0.92)],
                startPoint: .top,
                endPoint: .bottom
            )

            ctaButton(title: "유료 플랜 구독하고 전체 보기", lockIcon: true) {
                withAnimation(.easeOut(duration: 0.25)) { state = .analysis }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.5)))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.black.opacity(0.07)))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func fakeLine(width: CGFloat) -> some View {
        Capsule()
            .fill(navy.opacity(0.25))
            .frame(height: 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .scaleEffect(x: width, anchor: .leading)
    }

    private func ctaButton(title: String, lockIcon: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 7) {
                if lockIcon {
                    Image(systemName: "lock.open.fill")
                        .font(.system(size: 11, weight: .semibold))
                }
                Text(title)
            }
            .font(.pretendard(13, .bold))
            .foregroundStyle(Color.white)
            .padding(.horizontal, 22)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(LinearGradient(colors: [navy, navyDark], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .shadow(color: navy.opacity(0.45), radius: 10, y: 4)
            )
        }
        .buttonStyle(PressableButtonStyle(scale: 0.96))
    }

    // MARK: - State 2 · 습관 분석 (리스트 + 막대그래프)

    private func analysisState(_ report: MagicNoteClient.Report) -> some View {
        let habits: [Mistake] = Array(report.topMistakes.prefix(3))
        let maxCount = habits.map(\.count).max() ?? 0

        return VStack(alignment: .leading, spacing: 22) {
            Text("최근 작성한 문장들을 분석해\n반복되는 핵심 습관을 발견했어요.")
                .font(.pretendard(19, .medium))
                .lineSpacing(6)
                .foregroundStyle(Color.black.opacity(0.85))

            if habits.isEmpty {
                Text("아직 분석할 습관 데이터가 부족해요.")
                    .font(.pretendard(13))
                    .foregroundStyle(Color.black.opacity(0.4))
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
            } else {
                HStack(alignment: .center, spacing: 28) {
                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(Array(habits.enumerated()), id: \.offset) { index, mistake in
                            HStack(alignment: .top, spacing: 12) {
                                Text("\(index + 1)")
                                    .font(.pretendard(12, .bold))
                                    .foregroundStyle(navy)
                                    .frame(width: 26, height: 26)
                                    .background(Circle().fill(navy.opacity(0.12)))

                                Text(mistake.label)
                                    .font(.pretendard(13.5))
                                    .lineSpacing(4)
                                    .foregroundStyle(Color.black.opacity(0.72))
                            }
                        }
                    }

                    Spacer(minLength: 0)

                    HabitBarChart(bars: barData(habits, maxCount: maxCount), accent: navy)
                        .frame(maxWidth: 200)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                HStack {
                    Spacer()
                    ctaButton(title: "같이 고쳐볼까요?") {
                        withAnimation(.easeOut(duration: 0.25)) { state = .correction }
                    }
                }
            }
        }
    }

    /// 교정 횟수를 최댓값 기준 백분율로 환산해 그래프 데이터를 만든다.
    private func barData(_ habits: [Mistake], maxCount: Int) -> [HabitBarChart.Bar] {
        guard maxCount > 0 else { return [] }
        return habits.map { mistake in
            HabitBarChart.Bar(
                label: shorten(mistake.label),
                percent: Int((Double(mistake.count) / Double(maxCount) * 100).rounded())
            )
        }
    }

    /// 그래프 축 라벨용 — 습관 문구를 짧게 줄인다.
    private func shorten(_ label: String) -> String {
        let cleaned = label
            .replacingOccurrences(of: "표현", with: "")
            .replacingOccurrences(of: "사용", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return String(cleaned.prefix(8))
    }

    // MARK: - State 3 · 습관 교정 제안

    private func correctionState(_ report: MagicNoteClient.Report) -> some View {
        let corrections = buildCorrections(report)

        return VStack(alignment: .leading, spacing: 18) {
            Text("같이 고쳐볼까요?")
                .font(.pretendard(19, .medium))
                .foregroundStyle(Color.black.opacity(0.85))

            ScrollView(showsIndicators: false) {
                VStack(spacing: 12) {
                    ForEach(Array(corrections.enumerated()), id: \.offset) { index, correction in
                        correctionCard(correction, index: index)
                    }

                    if corrections.isEmpty {
                        Text("제안할 교정 항목이 없어요. 훌륭해요!")
                            .font(.pretendard(13))
                            .foregroundStyle(Color.black.opacity(0.4))
                            .padding(.top, 40)
                    }
                }
            }
        }
    }

    /// topMistakes + suggestions를 인덱스 기준으로 묶어 교정 카드 데이터를 만든다.
    private func buildCorrections(_ report: MagicNoteClient.Report) -> [Correction] {
        report.topMistakes.enumerated().map { index, mistake in
            Correction(
                habit: mistake.label,
                description: report.suggestions.count > index ? report.suggestions[index] : nil,
                before: mistake.before,
                after: mistake.after
            )
        }
    }

    private func correctionCard(_ correction: Correction, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("\(index + 1). \(correction.habit)")
                .font(.pretendard(13.5, .bold))
                .foregroundStyle(navy)

            if let description = correction.description {
                Text(description)
                    .font(.pretendard(11.5))
                    .lineSpacing(4)
                    .foregroundStyle(Color.black.opacity(0.62))
            }

            if let before = correction.before, let after = correction.after {
                HStack(alignment: .center, spacing: 10) {
                    Text(before)
                        .font(.pretendard(11))
                        .strikethrough(color: Color(red: 0xb0 / 255, green: 0x5a / 255, blue: 0x5b / 255).opacity(0.5))
                        .foregroundStyle(Color.black.opacity(0.45))
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .center)

                    Image(systemName: "arrow.right")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(navy)

                    Text(after)
                        .font(.pretendard(11.5, .semibold))
                        .foregroundStyle(Color.black.opacity(0.82))
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                .padding(.top, 10)
                .overlay(alignment: .top) {
                    Rectangle().fill(navy.opacity(0.1)).frame(height: 1)
                }
            }
        }
        .padding(15)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.6)))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.black.opacity(0.07)))
    }

    // MARK: - 데이터 로드

    private func loadIfNeeded() {
        if report == nil, errorMessage == nil, !isLoading {
            onLoad()
        }
    }
}

// MARK: - 습관 빈도 막대그래프 (외부 차트 라이브러리 없이 순수 Shape)

private struct HabitBarChart: View {
    struct Bar: Identifiable {
        let id = UUID()
        let label: String
        let percent: Int
    }

    let bars: [Bar]
    let accent: Color
    @State private var grown = false

    var body: some View {
        HStack(alignment: .bottom, spacing: 20) {
            ForEach(Array(bars.enumerated()), id: \.element.id) { index, bar in
                VStack(spacing: 6) {
                    Text("\(bar.percent)%")
                        .font(.pretendard(10, .bold))
                        .foregroundStyle(accent)

                    ZStack(alignment: .bottom) {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(accent.opacity(0.08))
                        RoundedRectangle(cornerRadius: 6)
                            .fill(accent.opacity(0.85))
                            .scaleEffect(y: grown ? CGFloat(bar.percent) / 100 : 0.001, anchor: .bottom)
                            .animation(.spring(response: 0.5, dampingFraction: 0.8).delay(Double(index) * 0.1), value: grown)
                    }
                    .frame(width: 34, height: 104)

                    Text(bar.label)
                        .font(.pretendard(8.5, .semibold))
                        .foregroundStyle(Color.black.opacity(0.5))
                        .lineLimit(1)
                }
            }
        }
        .onAppear {
            grown = false
            withAnimation(.easeOut(duration: 0.05)) { grown = true }
        }
    }
}
