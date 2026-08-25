#!/usr/bin/env python3
"""테스트 3: 현재 포커스된 입력창의 텍스트 직접 읽기.

터미널에서 실행하면 터미널 자체에 포커스가 있으므로 지연 실행을 쓰세요:

    sleep 5; python3 03_ax_read_focused.py   # 5초 안에 카톡 입력창 클릭

성공하면 입력창에 있는 '아직 보내지 않은' 텍스트가 그대로 출력됩니다.
"""
import time

import ApplicationServices as AS


def get_focused_element():
    system_el = AS.AXUIElementCreateSystemWide()
    err, el = AS.AXUIElementCopyAttributeValue(system_el, "AXFocusedApplication", None)
    if err != 0 or el is None:
        print(f"❌ 포커스된 앱을 못 가져옴 (err={err}). 손쉬운 사용 권한 확인!")
        return None
    err, focused = AS.AXUIElementCopyAttributeValue(el, "AXFocusedUIElement", None)
    if err != 0 or focused is None:
        print(f"❌ 포커스된 요소 없음 (err={err}).")
        return None
    return focused


def main():
    print("포커스된 입력창 값을 읽습니다...\n")
    el = get_focused_element()
    if el is None:
        return

    role = AS.AXUIElementCopyAttributeValue(el, "AXRole", None)[1] or "?"
    app = AS.AXUIElementCopyAttributeValue(el, "AXFocusedWindow", None)
    value = AS.AXUIElementCopyAttributeValue(el, "AXValue", None)[1]

    print(f"role : {role}")
    print(f"value: {value!r}")
    print()
    if value:
        print("✅ 성공! 접근성 API만으로 미발송 텍스트를 읽을 수 있습니다.")
    else:
        print("⚠️  값이 비어 있습니다. 입력창에 텍스트가 있는 상태에서 다시 시도하세요.")


if __name__ == "__main__":
    main()
