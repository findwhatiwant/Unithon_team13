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

# .env의 시크릿을 앱 리소스로 주입 (소스/깃에는 포함되지 않음)
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
  GEMINI_KEY=$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r')
  if [ -n "${GEMINI_KEY:-}" ]; then
    /usr/libexec/PlistBuddy -c "Add :GEMINI_API_KEY string $GEMINI_KEY" \
      "dist/$APP_NAME.app/Contents/Resources/Secrets.plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :GEMINI_API_KEY $GEMINI_KEY" \
      "dist/$APP_NAME.app/Contents/Resources/Secrets.plist"
  fi
fi
echo ""
echo "빌드 완료: macos-app/dist/$APP_NAME.app"
