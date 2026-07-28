# work-report

从 GitLab 拉取本周提交，调用 LLM 归纳生成周报。

## 模块划分

```
work-report/
├── main.py                      # 入口
├── .env / .env.example          # 配置
├── requirements.txt
├── scripts/
│   ├── run_scheduled.bat        # 定时任务入口
│   └── install_scheduled_task.ps1
└── work_report/
    ├── config.py                # 读取 .env
    ├── holiday.py               # 节假日 / 放假前最后工作日判断
    ├── gitlab_fetcher.py        # 获取 GitLab 提交
    └── llm_summarizer.py        # 调用 LLM 生成周报
```

| 模块 | 职责 |
|------|------|
| `holiday` | 判断今天是否为放假前最后一个工作日（今天工作日且明天非工作日） |
| `gitlab_fetcher` | 按项目 ID 拉取本周提交，按作者邮箱过滤 |
| `llm_summarizer` | 将提交文本交给 LLM，按项目分组归纳并生成下周计划 |
| `dingtalk_sender` | 通过群机器人 Webhook 发送周报到钉钉 |
| `config` | 从 `.env` 加载配置 |

> 不包含钉钉发送逻辑。节假日日历为离线配置（2026 国务院安排），无需外网。

## 环境准备

```bash
# 1. 创建并激活虚拟环境（Windows Git Bash）
python -m venv .venv
source .venv/Scripts/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 GITLAB_TOKEN、LLM_API_KEY 等
```

## 配置说明

| 变量 | 说明 |
|------|------|
| `GITLAB_URL` | GitLab 根地址（无末尾斜杠） |
| `GITLAB_TOKEN` | Private Access Token |
| `AUTHOR_EMAIL` | 用于过滤自己的提交 |
| `PROJECT_IDS` | 项目 ID，逗号分隔 |
| `LLM_API_KEY` | LLM API Key |
| `LLM_BASE_URL` | OpenAI 兼容接口地址，如 `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名，如 `gpt-4o-mini` |
| `LLM_TIMEOUT` | 请求超时秒数 |
| `SCHEDULE_TIME` | 定时执行时间，24 小时制 `HH:mm`，如 `17:30` |
| `SCHEDULE_DAYS` | 触发星期，逗号分隔：`Mon,Tue,Wed,Thu,Fri` |
| `DINGTALK_WEBHOOK` | 钉钉自定义机器人 Webhook（可选，配置后自动发送） |
| `DINGTALK_SECRET` | 机器人加签密钥（可选，安全设置勾选「加签」时必填） |
| `DINGTALK_TIMEOUT` | 钉钉请求超时秒数 |
| `PROJECT_NAMES_FILE` | 项目中文名映射 JSON 路径，默认 `project_names.json` |

### 项目中文名映射

编辑根目录 [`project_names.json`](project_names.json)，避免 LLM 每次给项目起不同中文名：

```json
{
  "example_backend": "示例后端服务",
  "example_frontend": "示例前端应用",
  "example_frontend": "前端交互平台"
}
```

周报一级标题会稳定输出为：`示例后端服务（example_backend）`。  
未配置映射的项目只输出英文名，不会乱编中文。

`LLM_BASE_URL` 兼容 OpenAI / DeepSeek / 通义 / Ollama 等 OpenAI 协议服务。

修改 `SCHEDULE_TIME` / `SCHEDULE_DAYS` 后，需重新执行 `install_scheduled_task.ps1` 才会生效。

### 钉钉「只有自己的群」配置步骤

1. 钉钉新建群，只保留自己（可先拉一人再建群后移出，或直接建内部群）
2. 群设置 → 智能群助手 → 添加机器人 → **自定义**
3. 安全设置建议选 **加签**，复制 Webhook 与 SEC 密钥到 `.env`
4. 测试：`python main.py --test-dingtalk`

## 使用

```bash
# 生成周报（打印到终端）
python main.py

# 写入文件
python main.py -o output/weekly-report.txt

# JSON 输出（含元数据）
python main.py --json -o output/weekly-report.json

# 只拉 GitLab，不调 LLM（调试用）
python main.py --skip-llm

# 只检查节假日判断
python main.py --check-holiday

# 定时任务模式：仅在放假前最后一个工作日才生成
python main.py --if-last-workday

# 钉钉连通性测试
python main.py --test-dingtalk

# 强制发送钉钉 / 禁止发送钉钉
python main.py --send-dingtalk
python main.py --no-dingtalk

# 详细日志
python main.py -v
```

配置了 `DINGTALK_WEBHOOK` 后，生成周报成功会自动发到群；`--no-dingtalk` 可临时关闭。

## 定时任务（Windows）

每天（工作日）由计划任务触发；脚本内部先判断「明天是否非工作日」，再决定是否拉 GitLab / 调 LLM。

在 `.env` 中配置执行时间：

```env
SCHEDULE_TIME=17:30
SCHEDULE_DAYS=Mon,Tue,Wed,Thu,Fri
```

```powershell
# 注册计划任务（读取 .env 中的时间与星期）
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_scheduled_task.ps1

# 临时覆盖时间（不改 .env）
.\scripts\install_scheduled_task.ps1 -At 18:00
.\scripts\install_scheduled_task.ps1 -At 09:15 -Days "Mon,Wed,Fri"

# 手动跑一次
schtasks /Run /TN WorkReportWeekly
# 或
.\scripts\run_scheduled.bat
```

- 日志：`logs/scheduled-YYYY-MM-DD.log`
- 生成成功时周报：`output/weekly-report-YYYY-MM-DD.txt`
- 删除任务：`Unregister-ScheduledTask -TaskName WorkReportWeekly -Confirm:$false`

判定逻辑：

```
今天是工作日 且 明天是非工作日 → 放假前最后一个工作日 → 生成周报
否则跳过（exit 0）
```

非工作日 = 法定节假日 或（周末且非调休上班日）。日历见 `work_report/holiday.py`，每年按国务院通知更新 `HOLIDAYS` / `MAKEUP_WORKDAYS`。

## 周报输出格式

按项目分组，不含「本周工作总结」：

```
一、示例后端服务（example_backend）

1、……
2、……

二、前端交互平台（example_frontend）

1、……

下周工作计划

1、……
2、……
```
