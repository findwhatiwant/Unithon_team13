import { useEffect, useState } from "react";
import "./PlanReportModal.css";

const ACCENT = "#41456b";

type ModalState = 1 | 2 | 3;

const HABITS = [
  "불필요한 쿠션어 사용 빈도가 높아요",
  "문장 끝맺음이 수동적인 표현으로 반복돼요",
  "비유적 표현을 과도하게 사용하는 경향이 있어요",
];

const HABIT_BARS = [
  { label: "쿠션어 사용", value: 72 },
  { label: "수동태 표현", value: 58 },
  { label: "비유 사용 빈도", value: 85 },
];

const CORRECTIONS = [
  {
    habit: "1. 쿠션어를 여러 번 덧붙이는 표현",
    before: "혹시 괜찮으시다면 확인 부탁드려요",
    after: "확인 부탁드립니다",
    description:
      "배려를 표현하려는 좋은 의도이지만, 쿠션어가 겹치면 요청의 핵심이 흐려지고 자신 없어 보일 수 있어요. 먼저 필요한 일을 분명하게 말하고, 꼭 필요한 경우에만 부드러운 표현을 한 번 덧붙여 보세요.",
  },
  {
    habit: "2. 확신을 낮추는 문장 끝맺음",
    before: "제 생각에는 아마 이게 맞을 것 같아요",
    after: "이 방향이 맞다고 판단됩니다",
    description:
      "'아마', '것 같아요'가 반복되면 충분히 검토한 내용도 조심스럽거나 책임을 피하는 인상으로 들릴 수 있어요. 근거가 있을 때는 판단을 또렷하게 말하고, 불확실한 부분만 따로 밝혀 주세요.",
  },
  {
    habit: "3. 비유와 감정을 앞세우는 강조",
    before: "일정이 눈 깜짝할 사이에 폭탄처럼 다가올 것 같아요",
    after: "일정이 임박해 우선순위 조정이 필요합니다",
    description:
      "생생한 비유는 기억에 남지만, 업무나 요청 상황에서는 실제 문제와 필요한 행동을 가릴 수 있어요. 비유 대신 현재 상황, 영향, 다음 행동을 차례로 적으면 더 차분하고 설득력 있게 전달됩니다.",
  },
];

function HabitBarChart() {
  const chartHeight = 104;
  const barWidth = 32;
  const gap = 22;
  const width = HABIT_BARS.length * barWidth + (HABIT_BARS.length - 1) * gap + 16;

  return (
    <svg className="prm-chart" viewBox={`0 0 ${width} ${chartHeight + 42}`} role="img" aria-label="글쓰기 습관 빈도 막대그래프">
      {HABIT_BARS.map((bar, i) => {
        const x = 8 + i * (barWidth + gap);
        const h = (bar.value / 100) * chartHeight;
        const y = chartHeight - h + 16;
        return (
          <g key={bar.label}>
            <rect x={x} y="16" width={barWidth} height={chartHeight} rx="6" fill="rgba(65,69,107,0.08)" />
            <rect
              className="prm-chart-bar"
              style={{ animationDelay: `${i * 100}ms` }}
              x={x}
              y={y}
              width={barWidth}
              height={h}
              rx="6"
              fill={ACCENT}
              opacity="0.85"
            />
            <text x={x + barWidth / 2} y={y - 6} textAnchor="middle" fontSize="10" fontWeight={700} fill={ACCENT}>
              {bar.value}%
            </text>
            <text x={x + barWidth / 2} y={chartHeight + 33} textAnchor="middle" fontSize="8.5" fontWeight={600} fill="rgba(0,0,0,0.5)">
              {bar.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function PlanReportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [state, setState] = useState<ModalState>(1);

  useEffect(() => {
    if (open) setState(1);
  }, [open]);

  if (!open) return null;

  return (
    <div className="prm-backdrop" onClick={onClose}>
      <div className="prm-panel" onClick={e => e.stopPropagation()}>
        <button className="prm-close" onClick={onClose} aria-label="닫기">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 2l8 8M10 2l-8 8" stroke="rgba(0,0,0,0.5)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        {state === 1 && (
          <div className="prm-state prm-state-1">
            <p className="prm-lead">
              지금까지 쓰신 <strong>128개</strong>의 문장을 분석해서 <br />
              무의식적으로 사용하는 습관들을 발견했어요.
            </p>

            <div className="prm-teaser">
              <div className="prm-teaser-blur">
                <div className="prm-fake-line" style={{ width: "88%" }} />
                <div className="prm-fake-line" style={{ width: "72%" }} />
                <div className="prm-fake-line" style={{ width: "94%" }} />
                <div className="prm-fake-line" style={{ width: "60%" }} />
                <div className="prm-fake-line" style={{ width: "80%" }} />
                <div className="prm-fake-line" style={{ width: "70%" }} />
              </div>
              <div className="prm-teaser-fade" />
              <button className="prm-cta" onClick={() => setState(2)}>
                유료 플랜 구독하고 전체 보기
              </button>
            </div>
          </div>
        )}

        {state === 2 && (
          <div className="prm-state prm-state-2">
            <h2 className="prm-title">
              최근 작성한 문장들을 분석해
              <br />
              반복되는 핵심 습관을 발견했어요.
            </h2>

            <div className="prm-split">
              <ol className="prm-habit-list">
                {HABITS.map((habit, i) => (
                  <li key={habit}>
                    <span className="prm-habit-num">{i + 1}</span>
                    <span>{habit}</span>
                  </li>
                ))}
              </ol>

              <div className="prm-chart-box">
                <HabitBarChart />
              </div>
            </div>

            <div className="prm-footer-right">
              <button className="prm-cta" onClick={() => setState(3)}>
                같이 고쳐볼까요?
              </button>
            </div>
          </div>
        )}

        {state === 3 && (
          <div className="prm-state prm-state-3">
            <h2 className="prm-title">같이 고쳐볼까요?</h2>

            <div className="prm-correction-list">
              {CORRECTIONS.map(correction => (
                <div className="prm-correction-row" key={correction.habit}>
                  <p className="prm-correction-habit">{correction.habit}</p>
                  <p className="prm-correction-description">{correction.description}</p>
                  <div className="prm-correction-example">
                    <span className="prm-before">{correction.before}</span>
                    <span className="prm-arrow">→</span>
                    <span className="prm-after">{correction.after}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PlanReportModalDemo() {
  const [open, setOpen] = useState(false);

  return (
    <div className="prm-demo-page">
      <button className="prm-trigger" onClick={() => setOpen(true)} aria-label="유료 플랜 리포트 열기">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 2v16M2 10h16" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>

      <PlanReportModal open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

export { PlanReportModal };
