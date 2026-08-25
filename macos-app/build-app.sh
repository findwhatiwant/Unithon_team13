#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME=MagicNote
BIN_NAME=RefinerMenu

swift build -c release
cp ".build/release/$BIN_NAME" /tmp/"$BIN_NAME"
rm -rf "dist/$APP_NAME.app"
mkdir -p "dist/$APP_NAME.app/Contents/MacOS"
mv /tmp/"$BIN_NAME" "dist/$APP_NAME.app/Contents/MacOS/$BIN_NAME"

# SwiftPM 리소스 번들(임베드 폰트 등)을 .app에 포함 (번들 이름은 패키지 이름 기준)
mkdir -p "dist/$APP_NAME.app/Contents/Resources"
cp -R ".build/release/MessageRefiner_MenuBarApp.bundle" "dist/$APP_NAME.app/Contents/Resources/"

cat > "dist/$APP_NAME.app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>MagicNote</string>
    <key>CFBundleDisplayName</key>
    <string>Magic note</string>
    <key>CFBundleIdentifier</key>
    <string>com.unithon.team13.MagicNote</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleExecutable</key>
    <string>RefinerMenu</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

codesign --force --sign - "dist/$APP_NAME.app"

# ── 자기완결형 서버 런타임 번들 (저장소 없는 맥에서도 동작) ──────────
# CPython 런타임(python-build-standalone) + 의존성을 앱 리소스에 포함한다.
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7%2B20241016-aarch64-apple-darwin-install_only.tar.gz"
RUNTIME_DIR=".build/python-runtime"
SITE_PACKAGES=".build/server-bundle/site-packages"

if [ ! -x "$RUNTIME_DIR/python/bin/python3" ]; then
    echo "🐍 파이썬 런타임 다운로드 중..."
    mkdir -p "$RUNTIME_DIR"
    curl -sL "$PBS_URL" | tar xz -C "$RUNTIME_DIR"
fi

if [ ! -f "$SITE_PACKAGES/uvicorn/__init__.py" ]; then
    echo "📦 서버 의존성 설치 중..."
    rm -rf "$SITE_PACKAGES"
    mkdir -p "$SITE_PACKAGES"
    (cd .. && "$OLDPWD/$RUNTIME_DIR/python/bin/python3" -m pip install \
        -q --disable-pip-version-check --no-cache-dir \
        --target "$OLDPWD/$SITE_PACKAGES" .)
    # 불필요한 캐시 제거로 번들 경량화
    find "$SITE_PACKAGES" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
fi

echo "📚 앱 번들에 서버 런타임 복사 중..."
SERVER_RES="dist/$APP_NAME.app/Contents/Resources/server"
rm -rf "$SERVER_RES"
mkdir -p "$SERVER_RES"
cp -R "$RUNTIME_DIR/python" "$SERVER_RES/python"
cp -R "$SITE_PACKAGES" "$SERVER_RES/site-packages"

# .env의 시크릿을 앱 리소스로 주입 (소스/깃에는 포함되지 않음)
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
  SECRETS_PLIST="dist/$APP_NAME.app/Contents/Resources/Secrets.plist"
  for KEY in GEMINI_API_KEY SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY; do
    VAL=$(grep -E "^${KEY}=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r')
    if [ -n "${VAL:-}" ]; then
      /usr/libexec/PlistBuddy -c "Add :$KEY string $VAL" "$SECRETS_PLIST" 2>/dev/null || \
      /usr/libexec/PlistBuddy -c "Set :$KEY $VAL" "$SECRETS_PLIST"
    fi
  done
fi
echo ""
echo "빌드 완료: macos-app/dist/$APP_NAME.app ($(du -sh "dist/$APP_NAME.app" | cut -f1))"
