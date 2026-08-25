import { useEffect, useRef, useState } from "react";

type Step =
  | "idle"
  | "drafting"
  | "drafts"
  | "analyzing"
  | "analyzed"
  | "rewriting"
  | "done";

type Mode = "review" | "blocked";
type Purpose = "사과" | "거절" | "요청" | "피드백";

const MIRROR_FEEDBACK =
  "저희는 '부탁드립니다'가 상대방에게는 조금 부담을 줄 수 있다는 인상을 줄 수 있어요. '괜찮으시다면'과 같이 선택권을 주는 표현이 더 부드럽게 읽힙니다.";

const MIRROR_FINAL_TEXT =
  "괜찮으시다면 이번 회의 일정을 조정할 수 있을까요? 가능한 시간을 말씀해 주시면 맞추겠습니다.";

const STATUS_TAGS = [
  { label: "의도 보존 ✓", warn: false },
  { label: "톤 주의", warn: true },
  { label: "구조 ✓", warn: false },
  { label: "위험 단어 없음", warn: false },
];

const DRAFT_RESULTS = [
  {
    version: "기본형",
    text: "안녕하세요. 이번 프로젝트 일정과 관련하여 말씀드릴 사항이 있어 연락드립니다. 가능하시다면 내일 오전 중으로 간단히 미팅을 진행할 수 있을지 여쭤보고 싶습니다.",
  },
  {
    version: "부드럽게",
    text: "괜찮으시다면 이번 회의 일정을 조정할 수 있을까요? 가능한 시간을 말씀해 주시면 맞추겠습니다.",
  },
  {
    version: "명확하게",
    text: "금일 중 확인 필요하신 사항 전달드립니다. 회신 부탁드립니다.",
  },
];

const PURPOSES: Purpose[] = ["사과", "거절", "요청", "피드백"];

/* ── Shared primitives ─────────────────────────────────────── */

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="section-label">{children}</p>;
}

function LoadingRow({ label }: { label: string }) {
  return (
    <div className="loading-row">
      <span className="spinner" />
      <span className="shimmer-text">{label}</span>
    </div>
  );
}

/* ── Feed items ────────────────────────────────────────────── */

function UserBubble({ text }: { text: string }) {
  return (
    <div className="user-bubble-row">
      <div className="user-bubble">{text}</div>
    </div>
  );
}

function DraftListCard({
  selectedIdx,
  onSelect,
  copiedIdx,
  onCopy,
  onConfirm,
}: {
  selectedIdx: number;
  onSelect: (i: number) => void;
  copiedIdx: number | null;
  onCopy: (i: number, text: string) => void;
  onConfirm: () => void;
}) {
  return (
    <div className="feed-card">
      <SectionLabel>추천 초안 3가지</SectionLabel>
      <div className="draft-list">
        {DRAFT_RESULTS.map((r, i) => (
          <div
            key={i}
            onClick={() => onSelect(i)}
            className={`draft-card ${selectedIdx === i ? "draft-card-selected" : ""}`}
          >
            <div className="draft-card-top">
              <span className="result-version-badge">{r.version}</span>
              <button
                onClick={e => {
                  e.stopPropagation();
                  onCopy(i, r.text);
                }}
                className={`copy-btn ${copiedIdx === i ? "copy-btn-copied" : ""}`}
              >
                {copiedIdx === i ? (
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <path d="M2 5.5l2.5 2.5 4.5-4.5" stroke="#41456b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <rect x="3.5" y="1" width="6.5" height="7.5" rx="1.5" stroke="rgba(0,0,0,0.35)" strokeWidth="1.1" />
                    <rect x="1" y="2.5" width="6.5" height="7.5" rx="1.5" stroke="rgba(0,0,0,0.35)" strokeWidth="1.1" fill="white" />
                  </svg>
                )}
              </button>
            </div>
            <p className="result-text">{r.text}</p>
          </div>
        ))}
      </div>
      <button className="primary-btn" onClick={onConfirm}>
        선택하고 Mirror로 확인
      </button>
    </div>
  );
}

function AnalysisCard({ onConfirm }: { onConfirm: () => void }) {
  return (
    <div className="feed-card">
      <div className="feedback-box">
        <div className="feedback-header">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <circle cx="5.5" cy="5.5" r="4.5" stroke="rgb(190, 106, 110)" strokeWidth="1" />
            <path d="M5.5 3.5v3M5.5 7.5h.01" stroke="rgb(190, 106, 110)" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span className="feedback-label">이렇게 읽힐 수 있어요</span>
        </div>
        <p className="feedback-text">{MIRROR_FEEDBACK}</p>
      </div>

      <div className="status-section">
        <SectionLabel>분석 상태</SectionLabel>
        <div className="status-grid">
          {STATUS_TAGS.map(tag => (
            <div key={tag.label} className={`status-tag ${tag.warn ? "status-tag-warn" : ""}`}>
              {tag.label}
            </div>
          ))}
        </div>
      </div>

      <button className="primary-btn" onClick={onConfirm}>
        교정 문장 확인하기
      </button>
    </div>
  );
}

function FinalCard({ onCopy, copied }: { onCopy: () => void; copied: boolean }) {
  return (
    <div className="feed-card">
      <SectionLabel>최종 미리보기</SectionLabel>
      <div className="edit-preview-box">
        <p className="edit-preview-text">{MIRROR_FINAL_TEXT}</p>
      </div>
      <button className={`primary-btn ${copied ? "primary-btn-copied" : ""}`} onClick={onCopy}>
        {copied ? "복사 완료 ✓" : "복사하기"}
      </button>
    </div>
  );
}

/* ── Composer (bottom input area: mode toggle + chips + input) ─ */

function Composer({
  mode,
  onToggleMode,
  purpose,
  onPurposeChange,
  value,
  onChange,
  onSend,
  disabled,
}: {
  mode: Mode;
  onToggleMode: () => void;
  purpose: Purpose;
  onPurposeChange: (p: Purpose) => void;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  return (
    <div className="composer-wrap">
      <div className="composer-mode-row">
        <button
          className={`mood-btn ${mode === "blocked" ? "mood-btn-active" : ""}`}
          onClick={onToggleMode}
          disabled={disabled}
        >
          막혔어요
        </button>
      </div>

      {mode === "blocked" && (
        <div className="purpose-row">
          {PURPOSES.map(p => (
            <button
              key={p}
              className={`chip chip-flex ${purpose === p ? "chip-active" : ""}`}
              onClick={() => onPurposeChange(p)}
              disabled={disabled}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      <div className="composer-row">
        <input
          className="composer-input"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !disabled && onSend()}
          placeholder={
            mode === "blocked"
              ? "핵심 상황이나 생각을 자유롭게 적어보세요"
              : "작성 중이던 초안이나 답장을 입력해 보세요"
          }
          disabled={disabled}
        />
        <button className="composer-send-btn" onClick={onSend} disabled={disabled || !value.trim()}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 10.5V2.5M6.5 2.5L3 6M6.5 2.5L10 6" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/* ── Root ──────────────────────────────────────────────────── */

export default function App() {
  const [step, setStep] = useState<Step>("idle");
  const [mode, setMode] = useState<Mode>("review");
  const [purpose, setPurpose] = useState<Purpose>("요청");

  const [inputValue, setInputValue] = useState("");
  const [sentText, setSentText] = useState("");
  const [sentMode, setSentMode] = useState<Mode>("review");

  const [selectedDraftIdx, setSelectedDraftIdx] = useState(1);
  const [draftCopiedIdx, setDraftCopiedIdx] = useState<number | null>(null);
  const [finalCopied, setFinalCopied] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [step]);

  const isComposerLocked = step !== "idle";

  const handleToggleMode = () => {
    setMode(m => (m === "review" ? "blocked" : "review"));
  };

  const handleSend = () => {
    if (!inputValue.trim() || step !== "idle") return;
    setSentText(inputValue.trim());
    setSentMode(mode);
    setInputValue("");

    if (mode === "blocked") {
      setStep("drafting");
      window.setTimeout(() => setStep("drafts"), 1400);
    } else {
      setStep("analyzing");
      window.setTimeout(() => setStep("analyzed"), 1400);
    }
  };

  const handleDraftCopy = (i: number, text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setDraftCopiedIdx(i);
    window.setTimeout(() => setDraftCopiedIdx(null), 1400);
  };

  const handleConfirmDraft = () => {
    setStep("analyzing");
    window.setTimeout(() => setStep("analyzed"), 1400);
  };

  const handleConfirmRewrite = () => {
    setStep("rewriting");
    window.setTimeout(() => setStep("done"), 1400);
  };

  const handleFinalCopy = () => {
    navigator.clipboard.writeText(MIRROR_FINAL_TEXT).catch(() => {});
    setFinalCopied(true);
    window.setTimeout(() => setFinalCopied(false), 1800);
  };

  return (
    <div className="app-bg">
      <div className="app-frame">
        <div className="app-frame-glow" />
        <div className="app-frame-notch" />

        <div className="app-frame-content">
          <div className="feed-header">
            <div className="home-logo">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1.5L8.2 5.2H12L9 7.4L10.2 11.1L7 8.9L3.8 11.1L5 7.4L2 5.2H5.8L7 1.5Z" fill="white" opacity="0.95" />
              </svg>
            </div>
            <span className="home-title">Magic Note</span>
          </div>

          <div className="feed-scroll">
            {step === "idle" && (
              <div className="feed-empty">
                <h1 className="home-question">지금 메세지는 어떤 상태인가요?</h1>
              </div>
            )}

            {step !== "idle" && (
              <div className="feed-list">
                <UserBubble text={sentText} />

                {step === "drafting" && <LoadingRow label="상황에 맞는 초안 3개를 생성 중이에요..." />}

                {(step === "drafts") && (
                  <DraftListCard
                    selectedIdx={selectedDraftIdx}
                    onSelect={setSelectedDraftIdx}
                    copiedIdx={draftCopiedIdx}
                    onCopy={handleDraftCopy}
                    onConfirm={handleConfirmDraft}
                  />
                )}

                {step === "analyzing" && <LoadingRow label="상대방에게 어떻게 전달될지 분석 중이에요..." />}

                {(step === "analyzed" || step === "rewriting" || step === "done") && (
                  <AnalysisCard onConfirm={handleConfirmRewrite} />
                )}

                {step === "rewriting" && <LoadingRow label="문장을 교정 중이에요..." />}

                {step === "done" && <FinalCard onCopy={handleFinalCopy} copied={finalCopied} />}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="feed-footer">
            <Composer
              mode={mode}
              onToggleMode={handleToggleMode}
              purpose={purpose}
              onPurposeChange={setPurpose}
              value={inputValue}
              onChange={setInputValue}
              onSend={handleSend}
              disabled={isComposerLocked}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
