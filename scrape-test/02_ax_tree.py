#!/usr/bin/env python3
"""테스트 2: 접근성 API로 앱의 UI 요소 트리 탐색.

사용법:
    python3 02_ax_tree.py              # 실행 중인 GUI 앱 나열
    python3 02_ax_tree.py "카카오톡"    # 해당 앱의 AX 트리 출력 (깊이 제한 있음)
"""
import sys

import ApplicationServices as AS
from Foundation import NSRunningApplication, NSWorkspace


def list_apps():
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    print(f"{'PID':>7}  이름")
    for app in apps:
        if app.activationPolicy() == 0:  # regular GUI app
            print(f"{app.processIdentifier():>7}  {app.localizedName()}")


def ax_value(element, attr):
    return AS.AXUIElementCopyAttributeValue(element, attr, None)[1]


def walk(element, depth=0, max_depth=12):
    role_ref = AS.AXUIElementCopyAttributeValue(element, "AXRole", None)[1]
    role = role_ref or "?"
    title = AS.AXUIElementCopyAttributeValue(element, "AXTitle", None)[1] or ""
    value = AS.AXUIElementCopyAttributeValue(element, "AXValue", None)[1]
    desc = AS.AXUIElementCopyAttributeValue(element, "AXDescription", None)[1] or ""

    value_str = repr(value)[:80] if value is not None else ""
    info = f"{'  ' * depth}[{role}] title={title!r} desc={desc!r} {value_str}"
    interesting = role in ("AXTextArea", "AXTextField", "AXComboBox")
    if interesting:
        info += "   ★ 입력 요소 발견!"
    print(info)

    if depth >= max_depth:
        return
    try:
        children = ax_value(element, "AXChildren") or []
    except Exception:
        return
    for child in children:
        walk(child, depth + 1, max_depth)


def inspect(app_name):
    apps = [
        a for a in NSWorkspace.sharedWorkspace().runningApplications()
        if a.localizedName() == app_name
    ]
    if not apps:
        print(f"❌ '{app_name}' 실행 중인 앱 없음. 인자 없이 실행해 목록을 확인하세요.")
        sys.exit(1)
    pid = apps[0].processIdentifier()
    print(f"→ {app_name} (pid={pid}) 탐색 중...\n")

    system_el = AS.AXUIElementCreateSystemWide()
    app_el = AS.AXUIElementCreateApplication(pid)
    err, windows = AS.AXUIElementCopyAttributeValue(app_el, "AXWindows", None)
    if err != 0 or not windows:
        print(f"❌ 윈도우를 가져올 수 없음 (err={err}).")
        print("   → 손쉬운 사용 권한이 부여됐는지 확인하세요.")
        sys.exit(1)
    for w in windows:
        walk(w)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        list_apps()
        print("\n앱 이름을 인자로 넣으면 AX 트리를 탐색합니다:")
        print('  python3 02_ax_tree.py "카카오톡"')
    else:
        inspect(sys.argv[1])
