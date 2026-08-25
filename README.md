# Unithon Team13

보내기 전 메시지를 LLM으로 다듬어주는 맥/윈도우 프로그램.

## macOS 메뉴바 앱

메뉴바에 상주하는 아이콘을 클릭하면 팝업에서 메시지를 입력하고 다듬은 결과를 바로 복사할 수 있다.

```bash
cd macos-app
./build-app.sh          # swift build -c release + .app 번들 생성
open dist/MessageRefiner.app
```

- 첫 실행 시 팝업 상단에 Gemini API 키 입력 ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) — 한 번 저장하면 UserDefaults에 유지
- 모드: 교정 / 톤(존댓말·반말·비즈니스·친근함) / 요약
- `⌘ + Enter`로 다듬기, 결과는 클립보드 복사 버튼으로 복사
- 종료: 팝업 하단 "종료" 버튼
- 테스트: `swift run RefinerTests` (macos-app 디렉터리)

## Python AI 파이프라인

macOS 앱과 동일한 로직의 Python 구현체 (CLI 테스트·라이브러리 용도).

## Windows 시스템 트레이 앱

Windows 알림 영역(시스템 트레이)에 상주하는 앱을 실행할 수 있다. 트레이 아이콘을 클릭하면 작은 작업창이 열리고, 작업창에서 2A/2B MVP 기능을 바로 사용할 수 있다.

- 추천받기: 무슨 말을 해야 할지 모를 때 상황/상대/목적/말투를 입력하면 후보 문장 3개를 생성
- 말투 점검: 이미 쓴 문장을 상황에 맞게 Mirror 분석
- 앱 실행 시 로컬 백엔드 서버가 꺼져 있으면 자동으로 `http://127.0.0.1:8000` 서버를 시작
- `save_history=false`이면 원문/후보/분석 문구는 DB에 저장하지 않음

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -e ".[dev]"
copy .env.example .env
```

`.env`에 `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`를 채운 뒤 실행한다.

```powershell
.\.venv\Scripts\refiner-tray.exe
```

콘솔 창 없이 실행하고 싶으면 아래처럼 실행한다.

```powershell
.\.venv\Scripts\pythonw.exe -m refiner.windows_tray
```

실행 후 작업 표시줄 오른쪽의 숨겨진 아이콘 영역에서 노란 말풍선 아이콘을 찾고, 아이콘을 클릭해 작업창을 연다.

## 구조

```
refiner/
├── models.py     # Mode, Tone, RefineRequest, RefineResult
├── prompts.py    # 모드·톤별 프롬프트 템플릿
├── llm.py        # LLMClient 인터페이스 + GeminiClient (재시도 포함)
├── pipeline.py   # 검증 → 프롬프트 조립 → LLM 호출 → 파싱
├── server.py     # FastAPI 백엔드 서버
├── supabase_store.py # Supabase REST 저장소
├── windows_tray.py # Windows 시스템 트레이 앱
└── cli.py        # 터미널 실행기
tests/            # pytest (가짜 클라이언트 주입, API 키 불필요)
```

## 3가지 모드

| 모드 | 설명 |
|------|------|
| `polish` | 맞춤법·오타 교정 + 자연스러운 문장 다듬기 |
| `tone` | 톤 변환 (`formal` 존댓말 / `casual` 반말 / `business` 비즈니스 / `friendly` 친근함) |
| `summarize` | 핵심만 간결하게 요약 |

## 사용법

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # https://aistudio.google.com/apikey 에서 키 발급 후 입력

# 교정
.venv/bin/python -m refiner "안녕하세요 오늘 뭐해폈어?"

# 톤 변환 (비즈니스)
.venv/bin/python -m refiner "내일 회의 시간 변경 가능?" --mode tone --tone business

# 요약 + 상황 맥락 추가
.venv/bin/python -m refiner "긴 메시지..." --mode summarize --context "직속 상사에게"
```

## 라이브러리로 사용

```python
from refiner import GeminiClient, Mode, Pipeline, RefineRequest, Tone

pipeline = Pipeline(GeminiClient(api_key="..."))
result = pipeline.run(
    RefineRequest(text="내일 회의 시간 변경 가능?", mode=Mode.TONE, tone=Tone.BUSINESS)
)
if result.success:
    print(result.refined_text)
```

API 실패 시 예외 대신 `RefineResult(success=False, error=...)`를 반환하므로 GUI에서 안전하게 처리 가능.

## 테스트

```bash
.venv/bin/pytest -q
```

## 백엔드 서버 + Supabase

현재 MVP 백엔드는 2A/2B 흐름을 우선 지원한다.

- 2A: Quick Compose 후보 생성 후 선택한 문장을 Mirror로 분석
- 2B: 사용자가 직접 쓴 문장을 Mirror로 분석
- 3번 Coach 기능은 나중에 확장할 수 있도록 기록만 저장

### 1. Supabase 테이블 만들기

Supabase 프로젝트를 만든 뒤 SQL Editor에 `supabase_schema.sql` 내용을 그대로 붙여 넣고 실행한다.

생성되는 주요 테이블:

- `user_profiles`: 사용자 기본 정보
- `user_consents`: 기록 저장/Coach 사용 동의 정보
- `message_sessions`: 한 번의 작성/분석 작업 기록
- `compose_candidates`: Quick Compose 후보 문장
- `mirror_analyses`: Mirror 분석 결과

이미 생성된 Supabase 프로젝트에 컬럼만 추가할 때는 `supabase_migrations/001_add_style_profile_to_user_profiles.sql`을 SQL Editor에서 실행한다.

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env`에 아래 값을 채운다.

```bash
GEMINI_API_KEY=...
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
```

주의: `SUPABASE_SERVICE_ROLE_KEY`는 프론트에 절대 넣지 않는다. 백엔드 서버에서만 사용한다.

개인정보 보호를 위해 `save_history`가 `false`이면 사용자가 입력한 원문, 상황, 후보 문장, Mirror 분석 문구는 DB에 저장하지 않고 최소 작업 기록만 남긴다.

### 3. 서버 실행

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/refiner-api
```

Windows PowerShell에서는 보통 아래처럼 실행한다.

```powershell
.\.venv\Scripts\pip.exe install -e ".[dev]"
.\.venv\Scripts\refiner-api.exe
```

서버 주소:

```txt
http://127.0.0.1:8000
```

상태 확인:

```txt
GET /health
```

### 4. 프론트가 호출할 API

Quick Compose:

```txt
POST /api/compose
```

요청 예시:

```json
{
  "user_id": "사용자 ID",
  "recipient": "동아리 팀원",
  "context": "내일 회의 시간을 바꿔야 함",
  "purpose": "부탁",
  "tone": "부드럽게",
  "save_history": true
}
```

Mirror:

```txt
POST /api/mirror
```

요청 예시:

```json
{
  "user_id": "사용자 ID",
  "session_id": "Compose에서 받은 session_id",
  "candidate_id": "선택한 후보 ID",
  "text": "혹시 내일 회의 시간 바꿀 수 있을까요?",
  "source_type": "quick_compose_candidate",
  "save_history": true
}
```

직접 입력 Mirror는 `session_id`, `candidate_id` 없이 보내면 된다.
