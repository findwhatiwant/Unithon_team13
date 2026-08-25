FROM node:22-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.mjs index.html App.tsx index.css PlanReportModal.tsx PlanReportModal.css ./
COPY src ./src
RUN npm run build


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV REFINER_API_HOST=0.0.0.0

WORKDIR /app

COPY pyproject.toml README.md ./
COPY refiner ./refiner
RUN pip install --no-cache-dir .

COPY --from=frontend /app/dist ./dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn refiner.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
