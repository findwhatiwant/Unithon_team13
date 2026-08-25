# Magic Note 백엔드 — FastAPI + Gemini 파이프라인
# 시크릿(GEMINI_API_KEY, SUPABASE_*)은 이미지에 넣지 않고 실행 환경 변수로 주입한다.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY refiner ./refiner

RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn refiner.server:app --host 0.0.0.0 --port ${PORT}"]
