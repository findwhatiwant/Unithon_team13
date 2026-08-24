# Unithon Team13

보내기 전 메시지를 LLM으로 다듬어주는 맥/윈도우 프로그램의 AI 파이프라인.

## 구조

```
refiner/
├── models.py     # Mode, Tone, RefineRequest, RefineResult
├── prompts.py    # 모드·톤별 프롬프트 템플릿
├── llm.py        # LLMClient 인터페이스 + GeminiClient (재시도 포함)
├── pipeline.py   # 검증 → 프롬프트 조립 → LLM 호출 → 파싱
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
