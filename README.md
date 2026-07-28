# work-report

从 GitLab 拉取本周提交，调用 LLM 归纳生成周报；支持 CLI、Windows 定时任务，以及 **Web 管理端**（配置 / 运行历史 / 一键触发）。

## 功能概览

- 拉取 GitLab 本周提交（按作者邮箱过滤）
- LLM 按项目归纳周报 + 下周计划（强制项目中文名）
- 可选钉钉群机器人推送
- 放假前最后工作日门控（离线 2026 节假日日历）
- **管理后台**：Nginx Proxy Manager 风格侧栏；配置可视化；每次运行记录提交明细、日志、周报正文
- **SQLite** 持久化（`data/work_report.db`），便于后续 Docker 挂卷

## 目录结构

```
work-report/
├── main.py                 # CLI 入口
├── web_app.py              # Web 服务入口
├── .env / .env.example     # 首次 seed 用配置
├── project_names.json      # 首次 seed 用项目中文名
├── data/                   # SQLite（gitignore）
├── web/                    # Vue3 前端源码
├── web_dist/               # 前端构建产物（gitignore；FastAPI 托管）
├── scripts/                # Windows 定时任务
└── work_report/
    ├── pipeline.py         # CLI/Web 共用执行流水线
    ├── db/                 # SQLAlchemy + seed
    ├── services/           # 配置 / 运行服务
    ├── api/                # FastAPI 路由
    ├── config.py
    ├── gitlab_fetcher.py
    ├── llm_summarizer.py
    ├── holiday.py
    └── dingtalk_sender.py
```

## 环境准备

```bash
# 1. 虚拟环境
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash

# 2. Python 依赖
pip install -r requirements.txt

# 3. 配置（首次启动会导入 SQLite）
cp .env.example .env
# 编辑 .env：GITLAB_TOKEN、LLM_API_KEY、DINGTALK_* 等

# 4. 前端构建（产物输出到 web_dist/，已 gitignore，需本地或 CI 构建）
cd web && npm install && npm run build && cd ..
```

## 启动 Web 管理端

```bash
# 需先有 web_dist/（上一步 npm run build）
python web_app.py
# 默认 http://0.0.0.0:6790
# 文档 http://127.0.0.1:6790/docs
```

开发前端热更新：

```bash
# 终端 1
python web_app.py --reload

# 终端 2
cd web && npm run dev   # http://127.0.0.1:5173 ，/api 代理到 6790
```

### 管理页能力

| 页面 | 说明 |
|------|------|
| 仪表盘 | 运行统计、节假日判断、一键生成周报 |
| 运行记录 | 分页列表、状态筛选 |
| 运行详情 | 周报正文、Git 提交明细、执行日志、钉钉结果 |
| 系统配置 | GitLab / LLM / 钉钉等（密钥脱敏展示） |
| 项目名称 | GitLab 名 ↔ 中文名映射 CRUD |

配置保存在 SQLite；`.env` 仅用于**空库首次导入**。密钥字段留空保存 = 不修改。

环境变量 `DATA_DIR` 可指定数据目录（默认项目下 `data/`），Docker 时可挂载为 `/data`。

## CLI 用法

```bash
# 生成周报（默认若已配置钉钉则发送；结果写入 SQLite）
python main.py

# 不发钉钉 / 写入文件
python main.py --no-dingtalk -o output/weekly-report.txt

# 只拉提交不调 LLM
python main.py --skip-llm --no-dingtalk

# 定时任务：仅放假前最后工作日
python main.py --if-last-workday

# 节假日检查 / 钉钉测试
python main.py --check-holiday
python main.py --test-dingtalk
```

## 配置说明

| 变量 / 配置键 | 说明 |
|---------------|------|
| `GITLAB_URL` / `gitlab_url` | GitLab 根地址 |
| `GITLAB_TOKEN` / `gitlab_token` | Private Token |
| `AUTHOR_EMAIL` / `author_email` | 过滤作者 |
| `PROJECT_IDS` / `project_ids` | 项目 ID，逗号分隔 |
| `LLM_*` | OpenAI 兼容接口 |
| `DINGTALK_*` | 群机器人 Webhook / 加签 |
| `SCHEDULE_TIME` / `SCHEDULE_DAYS` | Windows 计划任务参考（改后需重装任务） |
| `DATA_DIR` | SQLite 目录 |

### 项目中文名

可在 Web「项目名称」维护，或编辑 `project_names.json` 后在**空库**时 seed。  
周报一级标题会校正为：`中文名（gitlab_project_name）`。

## Windows 定时任务

```powershell
# 以管理员 PowerShell
.\scripts\install_scheduled_task.ps1
```

任务调用 `scripts/run_scheduled.bat` → `python main.py --if-last-workday`。

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/dashboard` | 仪表盘 |
| GET/PUT | `/api/config` | 配置 |
| POST | `/api/config/test-dingtalk` | 测钉钉 |
| POST | `/api/config/test-llm` | 测 LLM（提示词：计算2+3等于多少） |
| GET/PUT | `/api/project-names` | 项目名映射 |
| GET/POST | `/api/runs` | 列表 / 触发（202） |
| GET | `/api/runs/{id}` | 详情（含 commits、logs、report） |

同时只允许一个任务运行；冲突返回 409。

## Docker 部署

多阶段构建：Node 编译前端 → Python 运行 Web（托管 `web_dist` + API）。数据目录 `DATA_DIR=/data`，SQLite 文件为 `/data/work_report.db`。

```bash
# 1. 准备配置（勿提交 .env）
cp .env.example .env
# 编辑 .env：GITLAB_* / LLM_* / DINGTALK_* 等

# 2. 构建并启动（宿主机 6790）
docker compose up -d --build

# 3. 访问
# 管理端 http://127.0.0.1:6790
# 健康检查 http://127.0.0.1:6790/api/health
# API 文档 http://127.0.0.1:6790/docs
```

常用命令：

```bash
docker compose logs -f          # 日志
docker compose restart          # 重启
docker compose down             # 停止（保留 ./data）
docker compose exec work-report python main.py --no-dingtalk   # 容器内 CLI
```

说明：

| 项 | 约定 |
|----|------|
| 端口 | `6790:6790` |
| 数据卷 | `./data` → 容器 `/data`（与本地开发共用同一目录时可直接沿用已有库） |
| 配置 | `env_file: .env` 注入环境变量；**空库**首次启动 seed 到 SQLite，之后以 Web 配置 / 库为准 |
| 前端 | 构建阶段 `npm ci && npm run build`，无需本机 Node |
| 鉴权 | 暂无，仅本机或受信内网 |

## 说明

- 节假日为离线配置（2026 国务院安排），每年更新 `holiday.py` 中的集合即可
- 管理端暂不鉴权，请仅在本机或受信内网使用
