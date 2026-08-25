import { useState } from "react";
import "./HomeScreen.css";

/**
 * Standalone Home screen component.
 * onNavigate: pass a handler compatible with your app's router/screen switcher.
 *   - onNavigate("input")                 → go to the "빠른 편집"(Quick Compose) screen
 *   - onNavigate("mirror-analysis", text) → go straight to Mirror analysis with the typed text
 */
export type HomeNavigateFn = (screen: string, text?: string) => void;

export default function HomeScreen({ onNavigate }: { onNavigate: HomeNavigateFn }) {
  const [quickText, setQuickText] = useState("");

  const handleSend = () => {
    if (!quickText.trim()) return;
    onNavigate("mirror-analysis", quickText);
  };

  return (
    <div className="home-container">
      <div className="home-header">
        <div className="home-logo">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1.5L8.2 5.2H12L9 7.4L10.2 11.1L7 8.9L3.8 11.1L5 7.4L2 5.2H5.8L7 1.5Z" fill="white" opacity="0.95" />
          </svg>
        </div>
        <span className="home-title">Magic Note</span>
      </div>

      <div className="divider" />

      <div className="home-hero">
        <h1 className="home-question">지금 메세지는 어떤 상태인가요?</h1>

        <button className="mood-btn" onClick={() => onNavigate("input")}>
          막혔어요
        </button>

        <div className="home-input-row">
          <input
            className="home-input"
            value={quickText}
            onChange={e => setQuickText(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSend()}
            placeholder="작성 중이던 초안이나 답장을 입력해 보세요"
          />
          <button className="home-send-btn" onClick={handleSend} disabled={!quickText.trim()}>
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M6.5 10.5V2.5M6.5 2.5L3 6M6.5 2.5L10 6" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      <div className="divider" />

      <div className="home-footer">
        <button className="footer-btn">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="6.5" cy="6.5" r="5.5" stroke="rgba(0,0,0,0.4)" strokeWidth="1.2" />
            <circle cx="6.5" cy="6.5" r="1.8" stroke="rgba(0,0,0,0.4)" strokeWidth="1.2" />
            <path d="M6.5 1v1.2M6.5 10.8V12M1 6.5h1.2M10.8 6.5H12" stroke="rgba(0,0,0,0.4)" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
