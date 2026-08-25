#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME=MessageRefiner
BIN_NAME=RefinerMenu

swift build -c release
cp ".build/release/$BIN_NAME" /tmp/"$BIN_NAME"
rm -rf "dist/$APP_NAME.app"
mkdir -p "dist/$APP_NAME.app/Contents/MacOS"
mv /tmp/"$BIN_NAME" "dist/$APP_NAME.app/Contents/MacOS/$BIN_NAME"

# SwiftPM 리소스 번들(임베드 폰트 등)을 .app에 포함
mkdir -p "dist/$APP_NAME.app/Contents/Resources"
cp -R ".build/release/${APP_NAME}_MenuBarApp.bundle" "dist/$APP_NAME.app/Contents/Resources/"

cat > "dist/$APP_NAME.app/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>MessageRefiner</string>
    <key>CFBundleDisplayName</key>
    <string>메시지 다듬기</string>
    <key>CFBundleIdentifier</key>
    <string>com.unithon.team13.MessageRefiner</string>
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
echo ""
echo "빌드 완료: macos-app/dist/$APP_NAME.app"
