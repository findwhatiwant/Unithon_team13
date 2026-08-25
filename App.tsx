import { useEffect, useRef, useState } from "react";

type Step =
  | "idle"
  | "drafting"
  | "drafts"
  | "analyzing"
  | "analyzed"
  | "rewriting"
  | "done"
  | "longReviewing"
  | "longDone";

type Mode = "review" | "blocked" | "longform";
type Purpose = "사과" | "거절" | "요청" | "피드백";
type DocumentType = "논문" | "메일" | "편지" | "블로그" | "기타";

type ComposeCandidate = {
  candidate_id: string;
  candidate_index: number;
  candidate_text: string;
  ai_reason?: string | null;
};

type ComposeResponse = {
  session_id: string;
  candidates: ComposeCandidate[];
};

type MirrorResponse = {
  session_id: string;
  analysis_id: string;
  intent_summary: string;
  perceived_tone: string;
  tone_evidence: string;
  risk_level: string;
  risk_reasons: string[];
  ai_reason: string;
  soft_rewrite: string;
  clear_rewrite: string;
  short_rewrite: string;
};

type LongReviewResponse = {
  session_id: string;
  edited_text: string;
  summary_text: string;
  key_points: string[];
  changes: string[];
  ai_reason: string;
};

type AuthResponse = {
  user_id: string;
  email?: string | null;
  nickname?: string | null;
  access_token: string;
  refresh_token?: string | null;
};

type AuthUser = {
  user_id: string;
  email?: string | null;
  nickname?: string | null;
  access_token: string;
};

type StyleAnalyzeResponse = {
  user_id: string;
  analyzed_messages: number;
  style_profile: string;
};

const FALLBACK_API_CANDIDATES = ["http://127.0.0.1:8001", "http://127.0.0.1:8000"];
const AUTH_STORAGE_KEY = "magic_note_auth_user";
const ANONYMOUS_USER_STORAGE_KEY = "magic_note_user_id";
const SAVE_HISTORY_STORAGE_KEY = "magic_note_save_history";
const PURPOSES: Purpose[] = ["사과", "거절", "요청", "피드백"];
const DOCUMENT_TYPES: DocumentType[] = ["논문", "메일", "편지", "블로그", "기타"];
const TONE_STYLES = ["정중하게", "부드럽게", "친근하게", "아련하게"];
const DRAFT_LABELS = ["기본형", "부드럽게", "명확하게"];

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

function UserBubble({ text }: { text: string }) {
  return (
    <div className="user-bubble-row">
      <div className="user-bubble">{text}</div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>;
}

function ContextPanel({
  counterpart,
  selfDescription,
  toneStyle,
  saveHistory,
  signedIn,
  onCounterpartChange,
  onSelfDescriptionChange,
  onToneStyleChange,
  onSaveHistoryChange,
  onAnalyzeStyle,
  styleBusy,
}: {
  counterpart: string;
  selfDescription: string;
  toneStyle: string | null;
  saveHistory: boolean;
  signedIn: boolean;
  onCounterpartChange: (value: string) => void;
  onSelfDescriptionChange: (value: string) => void;
  onToneStyleChange: (value: string | null) => void;
  onSaveHistoryChange: (value: boolean) => void;
  onAnalyzeStyle: () => void;
  styleBusy: boolean;
}) {
  return (
    <div className="context-panel">
      <div className="context-input-row">
        <input
          className="context-input"
          value={counterpart}
          onChange={e => onCounterpartChange(e.target.value)}
          placeholder="상대방"
        />
        <input
          className="context-input"
          value={selfDescription}
          onChange={e => onSelfDescriptionChange(e.target.value)}
          placeholder="나는"
        />
      </div>
      <div className="tone-chip-row">
        {TONE_STYLES.map(style => (
          <button
            type="button"
            key={style}
            className={`tone-chip ${toneStyle === style ? "tone-chip-active" : ""}`}
            onClick={() => onToneStyleChange(toneStyle === style ? null : style)}
          >
            {style}
          </button>
        ))}
      </div>
      <div className="profile-row">
        <label className={`history-toggle ${!signedIn ? "history-toggle-disabled" : ""}`}>
          <input
            type="checkbox"
            checked={saveHistory}
            onChange={e => onSaveHistoryChange(e.target.checked)}
            disabled={!signedIn}
          />
          <span>기록 저장</span>
        </label>
        <button type="button" className="profile-btn" onClick={onAnalyzeStyle} disabled={!signedIn || styleBusy}>
          {styleBusy ? "학습 중" : "내 말투 학습"}
        </button>
      </div>
    </div>
  );
}

function AccountPanel({
  mode,
  email,
  password,
  nickname,
  busy,
  message,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onNicknameChange,
  onSubmit,
}: {
  mode: "login" | "signup";
  email: string;
  password: string;
  nickname: string;
  busy: boolean;
  message: string | null;
  onModeChange: (mode: "login" | "signup") => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onNicknameChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="account-card">
      <div className="account-tabs">
        <button
          type="button"
          className={`account-tab ${mode === "login" ? "account-tab-active" : ""}`}
          onClick={() => onModeChange("login")}
        >
          로그인
        </button>
        <button
          type="button"
          className={`account-tab ${mode === "signup" ? "account-tab-active" : ""}`}
          onClick={() => onModeChange("signup")}
        >
          회원가입
        </button>
      </div>
      {mode === "signup" && (
        <input
          className="account-input"
          value={nickname}
          onChange={e => onNicknameChange(e.target.value)}
          placeholder="닉네임"
        />
      )}
      <input
        className="account-input"
        value={email}
        onChange={e => onEmailChange(e.target.value)}
        placeholder="이메일"
      />
      <input
        className="account-input"
        type="password"
        value={password}
        onChange={e => onPasswordChange(e.target.value)}
        onKeyDown={e => e.key === "Enter" && onSubmit()}
        placeholder={mode === "signup" ? "비밀번호 8자 이상" : "비밀번호"}
      />
      <button type="button" className="primary-btn account-submit" onClick={onSubmit} disabled={busy}>
        {busy ? "처리 중..." : mode === "signup" ? "계정 만들기" : "로그인하기"}
      </button>
      {message && <p className="account-message">{message}</p>}
    </div>
  );
}

function DraftListCard({
  drafts,
  selectedIdx,
  onSelect,
  copiedIdx,
  onCopy,
  onConfirm,
}: {
  drafts: ComposeCandidate[];
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
        {drafts.map((draft, i) => (
          <div
            key={draft.candidate_id}
            onClick={() => onSelect(i)}
            className={`draft-card ${selectedIdx === i ? "draft-card-selected" : ""}`}
          >
            <div className="draft-card-top">
              <span className="result-version-badge">{DRAFT_LABELS[i] ?? `후보 ${i + 1}`}</span>
              <button
                type="button"
                onClick={e => {
                  e.stopPropagation();
                  onCopy(i, draft.candidate_text);
                }}
                className={`copy-btn ${copiedIdx === i ? "copy-btn-copied" : ""}`}
                aria-label="추천 초안 복사"
              >
                {copiedIdx === i ? "✓" : "⧉"}
              </button>
            </div>
            <p className="result-text">{draft.candidate_text}</p>
            {draft.ai_reason && <p className="result-reason">{draft.ai_reason}</p>}
          </div>
        ))}
      </div>
      <button type="button" className="primary-btn" onClick={onConfirm}>
        선택하고 Mirror로 확인
      </button>
    </div>
  );
}

function AnalysisCard({ data, onConfirm }: { data: MirrorResponse; onConfirm: () => void }) {
  const isWarn = data.risk_level === "보통" || data.risk_level === "높음";
  const feedback =
    data.ai_reason ||
    data.tone_evidence ||
    data.risk_reasons.join("\n") ||
    "문장의 의도는 유지하면서 상대가 더 편하게 읽을 수 있도록 표현을 다듬을 수 있어요.";

  const statusTags = [
    { label: "의도 보존 ✓", warn: false },
    { label: isWarn ? "톤 주의" : "톤 안정 ✓", warn: isWarn },
    { label: "구조 ✓", warn: false },
    { label: isWarn ? `위험도 ${data.risk_level}` : "위험 단어 없음", warn: isWarn },
  ];

  return (
    <div className="feed-card">
      <div className="feedback-box">
        <div className="feedback-header">
          <span className="feedback-icon">!</span>
          <span className="feedback-label">이렇게 읽힐 수 있어요</span>
        </div>
        <p className="feedback-text">{feedback}</p>
      </div>

      <div className="status-section">
        <SectionLabel>분석 상태</SectionLabel>
        <div className="status-grid">
          {statusTags.map(tag => (
            <div key={tag.label} className={`status-tag ${tag.warn ? "status-tag-warn" : ""}`}>
              {tag.label}
            </div>
          ))}
        </div>
      </div>

      <button type="button" className="primary-btn" onClick={onConfirm}>
        교정 문장 확인하기
      </button>
    </div>
  );
}

function FinalCard({ text, onCopy, copied }: { text: string; onCopy: () => void; copied: boolean }) {
  return (
    <div className="feed-card">
      <SectionLabel>최종 미리보기</SectionLabel>
      <div className="edit-preview-box">
        <p className="edit-preview-text">{text}</p>
      </div>
      <button type="button" className={`primary-btn ${copied ? "primary-btn-copied" : ""}`} onClick={onCopy}>
        {copied ? "복사 완료 ✓" : "복사하기"}
      </button>
    </div>
  );
}

function LongReviewCard({
  data,
  onCopyEdited,
  onCopySummary,
}: {
  data: LongReviewResponse;
  onCopyEdited: () => void;
  onCopySummary: () => void;
}) {
  return (
    <div className="feed-card">
      <SectionLabel>자동 요약</SectionLabel>
      <div className="edit-preview-box">
        <p className="edit-preview-text">{data.summary_text}</p>
      </div>

      <SectionLabel>핵심 포인트</SectionLabel>
      <div className="edit-preview-box">
        <ul className="result-list">
          {data.key_points.map(point => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>

      <SectionLabel>첨삭본</SectionLabel>
      <div className="edit-preview-box">
        <p className="edit-preview-text">{data.edited_text}</p>
      </div>

      <SectionLabel>수정 포인트</SectionLabel>
      <div className="edit-preview-box">
        <ul className="result-list">
          {data.changes.map(change => (
            <li key={change}>{change}</li>
          ))}
        </ul>
      </div>

      {data.ai_reason && (
        <>
          <SectionLabel>첨삭 근거</SectionLabel>
          <p className="long-review-reason">{data.ai_reason}</p>
        </>
      )}

      <div className="action-row">
        <button type="button" className="primary-btn" onClick={onCopyEdited}>
          첨삭본 복사
        </button>
        <button type="button" className="primary-btn primary-btn-copied" onClick={onCopySummary}>
          요약 복사
        </button>
      </div>
    </div>
  );
}

function Composer({
  mode,
  onModeChange,
  purpose,
  onPurposeChange,
  documentType,
  onDocumentTypeChange,
  value,
  onChange,
  onSend,
  disabled,
}: {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  purpose: Purpose;
  onPurposeChange: (p: Purpose) => void;
  documentType: DocumentType;
  onDocumentTypeChange: (type: DocumentType) => void;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const placeholder =
    mode === "blocked"
      ? "핵심 상황이나 생각을 자유롭게 적어보세요"
      : mode === "longform"
        ? `${documentType} 글을 붙여넣으면 첨삭과 요약을 해드려요`
        : "작성 중이던 초안이나 답장을 입력해 보세요";

  return (
    <div className="composer-wrap">
      <div className="composer-mode-row">
        <button
          type="button"
          className={`mood-btn ${mode === "blocked" ? "mood-btn-active" : ""}`}
          onClick={() => onModeChange(mode === "blocked" ? "review" : "blocked")}
          disabled={disabled}
        >
          막혔어요
        </button>
        <button
          type="button"
          className={`mood-btn long-mode-btn ${mode === "longform" ? "long-mode-btn-active" : ""}`}
          onClick={() => onModeChange(mode === "longform" ? "review" : "longform")}
          disabled={disabled}
        >
          긴글 첨삭
        </button>
      </div>

      {mode === "blocked" && (
        <div className="purpose-row">
          {PURPOSES.map(p => (
            <button
              type="button"
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

      {mode === "longform" && (
        <div className="purpose-row">
          {DOCUMENT_TYPES.map(type => (
            <button
              type="button"
              key={type}
              className={`chip chip-flex ${documentType === type ? "chip-active" : ""}`}
              onClick={() => onDocumentTypeChange(type)}
              disabled={disabled}
            >
              {type}
            </button>
          ))}
        </div>
      )}

      <div className={`composer-row ${mode === "longform" ? "composer-row-long" : ""}`}>
        {mode === "longform" ? (
          <textarea
            className="composer-input composer-textarea"
            value={value}
            onChange={e => onChange(e.target.value)}
            onKeyDown={e => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !disabled) onSend();
            }}
            placeholder={placeholder}
            disabled={disabled}
          />
        ) : (
          <input
            className="composer-input"
            value={value}
            onChange={e => onChange(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !disabled && onSend()}
            placeholder={placeholder}
            disabled={disabled}
          />
        )}
        <button className="composer-send-btn" onClick={onSend} disabled={disabled || !value.trim()} type="button">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 10.5V2.5M6.5 2.5L3 6M6.5 2.5L10 6" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

async function requestJson<T>(baseUrl: string, path: string, payload?: unknown): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: payload ? "POST" : "GET",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || `${response.status} ${response.statusText}`;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      message = parsed.detail || message;
    } catch {
      // Keep the plain response body when the server does not return JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

async function discoverApiBase(): Promise<string> {
  const sameOrigin = window.location.origin;
  const candidates = [sameOrigin, ...FALLBACK_API_CANDIDATES].filter(
    (base, index, list) => list.indexOf(base) === index,
  );

  for (const base of candidates) {
    try {
      const health = await requestJson<{ ok: boolean }>(base, "/health");
      if (health.ok) return base;
    } catch {
      // Try the next local backend port.
    }
  }
  throw new Error("로컬 백엔드 서버를 찾지 못했습니다.");
}

function finalTextFromMirror(result: MirrorResponse | null): string {
  if (!result) return "";
  return result.soft_rewrite || result.clear_rewrite || result.short_rewrite;
}

function readStoredAuthUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    return parsed.user_id && parsed.access_token ? parsed : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [step, setStep] = useState<Step>("idle");
  const [mode, setMode] = useState<Mode>("review");
  const [purpose, setPurpose] = useState<Purpose>("요청");
  const [documentType, setDocumentType] = useState<DocumentType>("메일");
  const [counterpart, setCounterpart] = useState("");
  const [selfDescription, setSelfDescription] = useState("");
  const [toneStyle, setToneStyle] = useState<string | null>("부드럽게");

  const [apiBase, setApiBase] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => readStoredAuthUser());
  const [userId, setUserId] = useState<string | null>(() => {
    const storedAuthUser = readStoredAuthUser();
    return storedAuthUser?.user_id ?? localStorage.getItem(ANONYMOUS_USER_STORAGE_KEY);
  });
  const [saveHistory, setSaveHistory] = useState(() => {
    const storedAuthUser = readStoredAuthUser();
    return Boolean(storedAuthUser && localStorage.getItem(SAVE_HISTORY_STORAGE_KEY) === "1");
  });
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authNickname, setAuthNickname] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [styleBusy, setStyleBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [inputValue, setInputValue] = useState("");
  const [sentText, setSentText] = useState("");
  const [sentMode, setSentMode] = useState<Mode>("review");

  const [composeSessionId, setComposeSessionId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<ComposeCandidate[]>([]);
  const [selectedDraftIdx, setSelectedDraftIdx] = useState(0);
  const [draftCopiedIdx, setDraftCopiedIdx] = useState<number | null>(null);
  const [mirrorResult, setMirrorResult] = useState<MirrorResponse | null>(null);
  const [longReviewResult, setLongReviewResult] = useState<LongReviewResponse | null>(null);
  const [finalCopied, setFinalCopied] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      try {
        const base = await discoverApiBase();
        if (cancelled) return;
        setApiBase(base);

        const storedAuthUser = readStoredAuthUser();
        if (storedAuthUser) {
          setAuthUser(storedAuthUser);
          setUserId(storedAuthUser.user_id);
          setSaveHistory(localStorage.getItem(SAVE_HISTORY_STORAGE_KEY) === "1");
          return;
        }

        const storedAnonymousUserId = localStorage.getItem(ANONYMOUS_USER_STORAGE_KEY);
        if (storedAnonymousUserId) {
          setUserId(storedAnonymousUserId);
          return;
        }

        const created = await requestJson<{ user_id: string }>(base, "/api/users", {
          nickname: "react-user",
          provider: "react_frontend",
        });
        if (cancelled) return;
        localStorage.setItem(ANONYMOUS_USER_STORAGE_KEY, created.user_id);
        setUserId(created.user_id);
      } catch (error) {
        if (!cancelled) setErrorMessage(error instanceof Error ? error.message : "서버 연결 실패");
      }
    }

    connect();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [step, drafts, mirrorResult, longReviewResult]);

  const isComposerLocked = step !== "idle" || !apiBase;
  const signedIn = Boolean(authUser);
  const shouldPersistHistory = Boolean(authUser && saveHistory);

  const composedContext = (text: string) => {
    const parts: string[] = [];
    if (counterpart.trim()) parts.push(`받는 사람: ${counterpart.trim()}`);
    if (selfDescription.trim()) parts.push(`보내는 사람: ${selfDescription.trim()}`);
    if (toneStyle) parts.push(`원하는 어투: ${toneStyle}`);
    parts.push(`상황: ${text}`);
    return parts.join(" / ");
  };

  const handleAuthSubmit = async () => {
    if (!apiBase || !authEmail.trim() || !authPassword.trim()) return;
    setAuthBusy(true);
    setAuthMessage(null);
    setErrorMessage(null);

    try {
      const body =
        authMode === "signup"
          ? { email: authEmail.trim(), password: authPassword, nickname: authNickname.trim() || null }
          : { email: authEmail.trim(), password: authPassword };
      const data = await requestJson<AuthResponse>(
        apiBase,
        authMode === "signup" ? "/api/auth/signup" : "/api/auth/login",
        body,
      );
      if (!data.access_token) {
        setAuthMessage("계정은 생성됐어요. 이메일 확인이 켜져 있다면 확인 후 로그인해 주세요.");
        return;
      }

      const nextUser: AuthUser = {
        user_id: data.user_id,
        email: data.email,
        nickname: data.nickname,
        access_token: data.access_token,
      };
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextUser));
      localStorage.setItem(SAVE_HISTORY_STORAGE_KEY, "1");
      setAuthUser(nextUser);
      setUserId(nextUser.user_id);
      setSaveHistory(true);
      setAuthPassword("");
      setAuthMessage("로그인 완료. 이제 기록 저장과 말투 학습을 사용할 수 있어요.");
      setAccountPanelOpen(false);
      await requestJson(apiBase, "/api/consents", {
        user_id: nextUser.user_id,
        save_message_history: true,
        coach_analysis: true,
        sensitive_info_storage: false,
      }).catch(() => {});
    } catch (error) {
      setAuthMessage(error instanceof Error ? error.message : "로그인 처리 중 오류가 발생했습니다.");
    } finally {
      setAuthBusy(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.setItem(SAVE_HISTORY_STORAGE_KEY, "0");
    setAuthUser(null);
    setSaveHistory(false);
    setUserId(localStorage.getItem(ANONYMOUS_USER_STORAGE_KEY));
    setAuthMessage("로그아웃됐어요.");
    setAccountPanelOpen(false);
  };

  const handleSaveHistoryChange = async (nextValue: boolean) => {
    if (!authUser || !apiBase) {
      setAccountPanelOpen(true);
      setErrorMessage("기록 저장은 로그인한 사용자만 사용할 수 있어요.");
      return;
    }

    setSaveHistory(nextValue);
    localStorage.setItem(SAVE_HISTORY_STORAGE_KEY, nextValue ? "1" : "0");
    try {
      await requestJson(apiBase, "/api/consents", {
        user_id: authUser.user_id,
        save_message_history: nextValue,
        coach_analysis: nextValue,
        sensitive_info_storage: false,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "동의 정보 저장 중 오류가 발생했습니다.");
    }
  };

  const handleAnalyzeStyle = async () => {
    if (!authUser || !apiBase) {
      setAccountPanelOpen(true);
      setErrorMessage("말투 학습은 로그인 후 기록이 저장된 사용자만 사용할 수 있어요.");
      return;
    }

    setStyleBusy(true);
    setErrorMessage(null);
    try {
      const data = await requestJson<StyleAnalyzeResponse>(apiBase, "/api/style/analyze", {
        user_id: authUser.user_id,
        min_messages: 3,
      });
      setErrorMessage(`말투 학습 완료: 최근 문장 ${data.analyzed_messages}개를 반영했어요.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "말투 학습 중 오류가 발생했습니다.");
    } finally {
      setStyleBusy(false);
    }
  };

  const resetForNewMode = (nextMode: Mode) => {
    setMode(nextMode);
    setInputValue("");
    setErrorMessage(null);
  };

  const handleSend = async () => {
    if (!apiBase || !inputValue.trim() || step !== "idle") return;

    const text = inputValue.trim();
    setSentText(text);
    setSentMode(mode);
    setInputValue("");
    setErrorMessage(null);

    try {
      if (mode === "blocked") {
        setStep("drafting");
        const data = await requestJson<ComposeResponse>(apiBase, "/api/compose", {
          user_id: userId,
          recipient: counterpart.trim() || null,
          context: composedContext(text),
          purpose,
          tone: toneStyle ?? "부드럽게",
          save_history: shouldPersistHistory,
        });
        setComposeSessionId(data.session_id);
        setDrafts(data.candidates);
        setSelectedDraftIdx(Math.min(1, Math.max(0, data.candidates.length - 1)));
        setStep("drafts");
        return;
      }

      if (mode === "longform") {
        setStep("longReviewing");
        const data = await requestJson<LongReviewResponse>(apiBase, "/api/long-review", {
          user_id: userId,
          document_type: documentType,
          purpose: documentType,
          text,
          save_history: shouldPersistHistory,
        });
        setLongReviewResult(data);
        setStep("longDone");
        return;
      }

      setStep("analyzing");
      const data = await requestJson<MirrorResponse>(apiBase, "/api/mirror", {
        user_id: userId,
        text,
        source_type: "direct_input",
        recipient: counterpart.trim() || null,
        context: composedContext(text),
        purpose,
        tone: toneStyle,
        save_history: shouldPersistHistory,
      });
      setMirrorResult(data);
      setStep("analyzed");
    } catch (error) {
      setStep("idle");
      setErrorMessage(error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.");
    }
  };

  const handleDraftCopy = (i: number, text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setDraftCopiedIdx(i);
    window.setTimeout(() => setDraftCopiedIdx(null), 1400);
  };

  const handleConfirmDraft = async () => {
    if (!apiBase || !drafts[selectedDraftIdx]) return;
    const selected = drafts[selectedDraftIdx];
    setStep("analyzing");
    setErrorMessage(null);

    try {
      const data = await requestJson<MirrorResponse>(apiBase, "/api/mirror", {
        user_id: userId,
        session_id: composeSessionId,
        candidate_id: selected.candidate_id,
        text: selected.candidate_text,
        source_type: "quick_compose_candidate",
        recipient: counterpart.trim() || null,
        context: composedContext(sentText),
        purpose,
        tone: toneStyle ?? "부드럽게",
        save_history: shouldPersistHistory,
      });
      setMirrorResult(data);
      setStep("analyzed");
    } catch (error) {
      setStep("drafts");
      setErrorMessage(error instanceof Error ? error.message : "Mirror 분석 중 오류가 발생했습니다.");
    }
  };

  const handleConfirmRewrite = () => {
    setStep("rewriting");
    window.setTimeout(() => setStep("done"), 500);
  };

  const handleFinalCopy = () => {
    navigator.clipboard.writeText(finalTextFromMirror(mirrorResult)).catch(() => {});
    setFinalCopied(true);
    window.setTimeout(() => setFinalCopied(false), 1800);
  };

  const resetConversation = () => {
    setStep("idle");
    setSentText("");
    setDrafts([]);
    setComposeSessionId(null);
    setMirrorResult(null);
    setLongReviewResult(null);
    setFinalCopied(false);
    setErrorMessage(null);
  };

  const question =
    mode === "longform"
      ? "어떤 글을 첨삭할까요?"
      : mode === "blocked"
        ? "어떤 상황에서 막혔나요?"
        : "지금 메세지는 어떤 상태인가요?";
  const accountPanel =
    accountPanelOpen && !authUser ? (
      <AccountPanel
        mode={authMode}
        email={authEmail}
        password={authPassword}
        nickname={authNickname}
        busy={authBusy}
        message={authMessage}
        onModeChange={setAuthMode}
        onEmailChange={setAuthEmail}
        onPasswordChange={setAuthPassword}
        onNicknameChange={setAuthNickname}
        onSubmit={handleAuthSubmit}
      />
    ) : null;

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
            <button
              type="button"
              className={`account-btn ${authUser ? "account-btn-signed" : ""}`}
              onClick={() => (authUser ? handleLogout() : setAccountPanelOpen(open => !open))}
            >
              {authUser ? "로그아웃" : "로그인"}
            </button>
            <button type="button" className="reset-btn" onClick={resetConversation} aria-label="새 메시지">
              ◎
            </button>
          </div>

          <div className="feed-scroll">
            {step === "idle" && (
              <div className="feed-empty">
                <h1 className="home-question">{question}</h1>
                <ContextPanel
                  counterpart={counterpart}
                  selfDescription={selfDescription}
                  toneStyle={toneStyle}
                  saveHistory={saveHistory}
                  signedIn={signedIn}
                  onCounterpartChange={setCounterpart}
                  onSelfDescriptionChange={setSelfDescription}
                  onToneStyleChange={setToneStyle}
                  onSaveHistoryChange={handleSaveHistoryChange}
                  onAnalyzeStyle={handleAnalyzeStyle}
                  styleBusy={styleBusy}
                />
                {accountPanel}
                {errorMessage && <ErrorBanner message={errorMessage} />}
              </div>
            )}

            {step !== "idle" && (
              <div className="feed-list">
                {accountPanel}
                <UserBubble text={sentText} />

                {step === "drafting" && <LoadingRow label="상황에 맞는 초안 3개를 생성 중이에요..." />}
                {step === "longReviewing" && <LoadingRow label="긴 글을 첨삭하고 핵심을 요약 중이에요..." />}

                {step === "drafts" && (
                  <DraftListCard
                    drafts={drafts}
                    selectedIdx={selectedDraftIdx}
                    onSelect={setSelectedDraftIdx}
                    copiedIdx={draftCopiedIdx}
                    onCopy={handleDraftCopy}
                    onConfirm={handleConfirmDraft}
                  />
                )}

                {step === "analyzing" && <LoadingRow label="상대방에게 어떻게 전달될지 분석 중이에요..." />}

                {(step === "analyzed" || step === "rewriting" || step === "done") && mirrorResult && (
                  <AnalysisCard data={mirrorResult} onConfirm={handleConfirmRewrite} />
                )}

                {step === "rewriting" && <LoadingRow label="문장을 교정 중이에요..." />}

                {step === "done" && (
                  <FinalCard text={finalTextFromMirror(mirrorResult)} onCopy={handleFinalCopy} copied={finalCopied} />
                )}

                {step === "longDone" && longReviewResult && (
                  <LongReviewCard
                    data={longReviewResult}
                    onCopyEdited={() => navigator.clipboard.writeText(longReviewResult.edited_text).catch(() => {})}
                    onCopySummary={() => navigator.clipboard.writeText(longReviewResult.summary_text).catch(() => {})}
                  />
                )}

                {errorMessage && <ErrorBanner message={errorMessage} />}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="feed-footer">
            <Composer
              mode={mode}
              onModeChange={resetForNewMode}
              purpose={purpose}
              onPurposeChange={setPurpose}
              documentType={documentType}
              onDocumentTypeChange={setDocumentType}
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
