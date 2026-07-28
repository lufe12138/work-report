# syntax=docker/dockerfile:1

# ---------- 前端构建 ----------
FROM node:20-alpine AS frontend
WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# vite outDir = ../web_dist → /build/web_dist
RUN npm run build

# ---------- 运行时 ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 证书（HTTPS 调 GitLab / LLM / 钉钉）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py web_app.py project_names.json ./
COPY work_report ./work_report
COPY --from=frontend /build/web_dist ./web_dist

RUN mkdir -p /data

EXPOSE 6790

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6790/api/health', timeout=3)"

CMD ["python", "web_app.py", "--host", "0.0.0.0", "--port", "6790"]
