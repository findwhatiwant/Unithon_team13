# 카톡 미발송 텍스트 자동 스크랩 테스트 (macOS)

macOS에서 다른 앱(카카오톡 등) 입력창의 **아직 보내지 않은 텍스트**를 읽어올 수 있는지 확인하는 스파이크 테스트.

## 준비

```bash
# 1. 접근성 권한 (AX 테스트에 필요)
#    시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용
#    → 터미널(또는 python3 실행 앱) 추가 & 활성화

python3 -m venv .venv-scrape
.venv-scrape/bin/pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa

# 2. 카톡(또는 아무 앱) 열고 입력창에 아무 텍스트나 입력해두기
```

## 테스트 1 — 클립보드 경유 방식 (가장 확실)

```bash
./01_clipboard_test.sh
```

- 실행 후 **3초 안에** 카톡 입력창을 클릭해두면, 자동으로 `⌘A → ⌘C` 해서 클립보드로 가져옴
- 모든 앱에서 동작. 단점: 클립보드 내용이 덮어씌워짐

## 테스트 2 — 접근성 API: 윈도우/요소 구조 탐색

```bash
.venv-scrape/bin/python 02_ax_tree.py "카카오톡"
```

- 해당 앱의 AX 트리를 뒤져 어떤 요소가 있는지 출력 (role + title + value)
- `AXTextArea`, `AXTextField` 가 보이면 접근성 방식 가능성 있음
- 인자 없으면 실행 중인 모든 앱 나열

## 테스트 3 — 접근성 API: 포커스된 입력창 값 직접 읽기

```bash
python3 03_ax_read_focused.py
```

- 현재 포커스된 UI 요소(`AXFocusedUIElement`)의 값을 읽음
- **터미널이 아니라 카톡 입력창에 커서를 두고**, 다른 터미널/지연 실행으로 돌려야 함
  ```bash
  sleep 5; .venv-scrape/bin/python 03_ax_read_focused.py   # 5초 안에 카톡 입력창 클릭
  ```

## 판정 기준

| 결과 | 의미 | 다음 단계 |
|------|------|-----------|
| 테스트 2·3에서 입력창 텍스트 읽힘 | AX 방식 가능 → 백그라운드에서 조용히 읽기 가능 | Swift로 AX 모니터링 설계 |
| 안 읽힘 (value 비었거나 요소 없음) | 카톡이 AX를 제한함 | 클립보드+전역단축키 방식으로 설계 |
| 테스트 1만 성공 | 범용 방식 채택 | ⌘A/⌘C 자동화 + 복원 로직 설계 |

> 참고: 이 폴더의 코드는 전부 탐색용 스파이크입니다. 동작 확인 후 실제 기능은 macos-app Swift 코드로 이식합니다.
