#!/bin/bash
# 테스트 1: 클립보드 경유 방식 — 입력창 전체선택 → 복사 → 클립보드에서 읽기
# 사용법: ./01_clipboard_test.sh
# 실행 후 3초 안에 카톡(또는 아무 앱)의 입력창을 클릭해두세요.

set -e

ORIG_CLIP=$(pbpaste 2>/dev/null || true)
echo "→ 기존 클립보드 백업 완료 (${#ORIG_CLIP}자)"
echo ""
echo "3초 안에 카톡 입력창을 클릭하세요..."
sleep 3

osascript <<'EOF'
tell application "System Events"
    keystroke "a" using command down
    delay 0.15
    keystroke "c" using command down
end tell
EOF

sleep 0.4
TEXT=$(pbpaste)

echo ""
echo "================================"
if [ -n "$TEXT" ]; then
    echo "✅ 스크랩된 미발송 텍스트:"
    echo "--------------------------------"
    echo "$TEXT"
    echo "--------------------------------"
    echo "(${#TEXT}자)"
else
    echo "⚠️  빈 텍스트가 복사됐습니다. 입력창에 커서와 텍스트가 있는지 확인하세요."
fi
echo "================================"

# 원래 클립보드 복원 (주석 해제해서 사용 — 지금은 확인용으로 유지)
# printf '%s' "$ORIG_CLIP" | pbcopy
