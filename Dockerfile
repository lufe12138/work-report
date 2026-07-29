# 不使用 # syntax=docker/dockerfile:1，避免构建前必须拉取 docker/dockerfile 前端镜像。
#
# 基础镜像默认走 DaoCloud 对 Docker Hub 的代理，避免国内直接访问 docker.io 失败。
# 网络通畅时可覆盖为官方：
#   docker compose build --build-arg NODE_IMAGE=node:20-alpine --build-arg PYTHON_IMAGE=python:3.12-slim

ARG NODE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.12-slim

# 包管理国内源（构建期）；可用 build-arg 覆盖
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# ---------- 前端构建 ----------
FROM ${NODE_IMAGE} AS frontend
ARG NPM_REGISTRY
WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci --registry="${NPM_REGISTRY}"

COPY web/ ./
# vite outDir = ../web_dist → /build/web_dist
RUN npm run build

# ---------- 运行时 ----------
FROM ${PYTHON_IMAGE} AS app
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

# 证书（HTTPS 调 GitLab / LLM / 钉钉）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt \
    -i "${PIP_INDEX_URL}" \
    --trusted-host "${PIP_TRUSTED_HOST}"

COPY main.py web_app.py project_names.json ./
COPY work_report ./work_report
COPY --from=frontend /build/web_dist ./web_dist

RUN mkdir -p /data

EXPOSE 6790

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6790/api/health', timeout=3)"

CMD ["python", "web_app.py", "--host", "0.0.0.0", "--port", "6790"]
