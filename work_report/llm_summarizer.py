"""LLM 周报归纳模块（OpenAI 兼容接口）。"""

from __future__ import annotations

import logging
import re

from openai import OpenAI

from work_report.config import Settings
from work_report.gitlab_fetcher import FetchResult

logger = logging.getLogger(__name__)

# LLM 配置页测活提示词
PING_PROMPT = "计算2+3等于多少"

# 匹配：一、任意标题（project_key） 或 一、project_key
_SECTION_TITLE_RE = re.compile(
    r"^([一二三四五六七八九十百千]+、)"  # 中文序号
    r"(.*?)"  # 标题中文部分（可空）
    r"（([a-zA-Z0-9_.\-]+)）"  # （gitlab_project_name）
    r"\s*$",
    re.MULTILINE,
)
_SECTION_TITLE_EN_ONLY_RE = re.compile(
    r"^([一二三四五六七八九十百千]+、)"
    r"([a-zA-Z0-9_.\-]+)"
    r"\s*$",
    re.MULTILINE,
)

SYSTEM_PROMPT = """你是一名资深研发工程师的周报助手。
请根据用户提供的 GitLab 提交记录，生成一份简洁、专业的中文周报。

严格要求：
1. 必须总结归纳，不能把每条提交逐条罗列。
2. 按 GitLab 项目分组；每个项目提炼成若干条高层次工作描述。
3. 每条描述要写成「做了什么 + 关键点/能力 + 价值/效果」的完整句，语言专业、连贯。
4. 纯文本输出，不要使用 markdown 标题（## ###）、加粗（**）或列表符号（- *）。
5. 一级分组用中文数字编号：一、二、三、；组内条目用 1、2、3、。
6. 一级标题格式必须为：业务中文名（gitlab_project_name）。
   - 若用户消息中提供了「项目中文名映射」，业务中文名必须与映射表完全一致，禁止同义改写、缩写或自行发挥。
   - 若某项目无映射，一级标题只写英文项目名，不要编造中文名。
7. 不要输出「本周工作总结」或任何总结段落。
8. 若没有提交记录，输出「本周暂无提交记录」即可，不要编造内容。
9. 不要编造提交中不存在的项目或明显无关的功能。

输出格式必须如下（不要增减大标题，不要加多余前后缀）：

一、[业务中文名]（[gitlab_project_name]）

1、[总结性工作描述]
2、[总结性工作描述]
...

二、[业务中文名]（[gitlab_project_name]）

1、[总结性工作描述]
...

下周工作计划

1、[基于本周工作合理推论的下周计划]
2、[基于本周工作合理推论的下周计划]
...

完整风格示例：

一、示例业务数据统计（example_backend）

1、完善数据统计查询体系，新增统计明细穿透查询能力与用户实时统计功能，支持按数据类型查询指标配置，优化周期对比指标处理与指标明细执行服务，提升统计数据的准确性与业务覆盖面。
2、推进编码标准化服务重构，优化业务编码与辅助编码标准化服务逻辑，基础数据统一使用平台标准码，优化输出选项编码域处理与合并指标类型处理，保障数据一致性与规范性。
3、新增内容检查智能体功能，支持质控分组分页查询与评估行类型合并处理，支持筛选组件类型配置，提升内容检查自动化能力。
4、增强任务管理模块灵活性，支持任务随机分页查询功能。
5、添加Scalar接口文档配置，替换字符串工具依赖，统一服务类换行符，提升代码可维护性。

二、示例前端应用（example_frontend）

1、构建流程核心服务能力，完善流程核心服务，新增发布中心与运行监控模块，补齐流程状态与Worker就绪校验，统一变量类型展示，为前端交互引擎奠定基础。
2、完善流程建模器功能，实现流程建模与条件编辑能力，修复分支条件展示、条件标签排版、流程变量布局等问题，提升建模器的可用性与交互体验。
3、集成接口文档配置，接入Scalar API文档并改用springdoc Scalar Starter，统一接口文档规范。
4、增加电商履约Worker编排示例，修复示例BPMN加载失败问题，适配后端统一接口契约，为业务接入提供参考实现。

下周工作计划

1、继续完善example_backend的编码标准化服务，推进数据统计模块的功能测试与性能优化。
2、开展内容检查智能体的集成测试与问题修复，梳理后续需求迭代计划。
3、推进example_frontend的流程引擎核心能力建设，完善Worker调度与状态管理机制。
4、优化流程建模器的交互体验，补充更多业务场景的编排示例与文档。
"""


def _date_only(value: str) -> str:
    """从 '2026-07-27 00:00:00' / ISO 中取出 YYYY-MM-DD。"""
    value = (value or "").strip()
    if not value:
        return ""
    return value[:10]


def format_report_header(week_start: str, week_end: str) -> str:
    """【周报】起始日期 ~ 结束日期"""
    start = _date_only(week_start)
    end = _date_only(week_end)
    if start and end:
        if start == end:
            return f"【周报】{start}"
        return f"【周报】{start} ~ {end}"
    if end:
        return f"【周报】{end}"
    if start:
        return f"【周报】{start}"
    return "【周报】"


def normalize_project_titles(report: str, name_map: dict[str, str]) -> str:
    """
    用 project_names.json 强制校正一级标题中文名。

    例如 LLM 写成「示例后端服务（example_backend）」
    会改回「示例后端服务（example_backend）」。
    """
    if not report or not name_map:
        return report

    def repl_full(match: re.Match[str]) -> str:
        prefix, project_key = match.group(1), match.group(3)
        zh = name_map.get(project_key, "").strip()
        if zh:
            fixed = f"{prefix}{zh}（{project_key}）"
            if match.group(0) != fixed:
                logger.info("校正项目标题: %s -> %s", match.group(0), fixed)
            return fixed
        # 无映射则去掉胡编中文，只保留英文名
        return f"{prefix}{project_key}"

    def repl_en(match: re.Match[str]) -> str:
        prefix, project_key = match.group(1), match.group(2)
        zh = name_map.get(project_key, "").strip()
        if zh:
            fixed = f"{prefix}{zh}（{project_key}）"
            logger.info("补全项目中文名: %s -> %s", match.group(0), fixed)
            return fixed
        return match.group(0)

    text = _SECTION_TITLE_RE.sub(repl_full, report)
    text = _SECTION_TITLE_EN_ONLY_RE.sub(repl_en, text)
    return text


def ensure_report_header(report: str, week_start: str, week_end: str) -> str:
    """确保正文开头带【周报】起止日期；若已有则替换为标准格式。"""
    header = format_report_header(week_start, week_end)
    body = (report or "").strip()
    if not body:
        return header

    # 去掉 LLM 可能自带的【周报】行
    lines = body.splitlines()
    if lines and lines[0].strip().startswith("【周报】"):
        rest = "\n".join(lines[1:]).lstrip()
        return f"{header}\n\n{rest}" if rest else header
    return f"{header}\n\n{body}"


class LLMSummarizer:
    """调用 OpenAI 兼容 API 将提交记录归纳为周报。"""

    def __init__(self, settings: Settings, client: OpenAI | None = None) -> None:
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
        )

    def build_user_prompt(self, fetch_result: FetchResult) -> str:
        """构造用户侧提示词。"""
        body = fetch_result.to_prompt_text()
        extra = ""
        if self.settings.project_name_map:
            extra = (
                "\n\n再次强调：一级标题中的业务中文名必须严格使用上文「项目中文名映射」，"
                "不得改成其他叫法。"
            )
        return (
            "请根据以下本周 GitLab 提交记录生成周报。\n\n"
            f"{body}{extra}"
        )

    def postprocess(self, content: str, fetch_result: FetchResult) -> str:
        """校正项目中文名，并加上起止日期标题。"""
        text = normalize_project_titles(content, self.settings.project_name_map)
        text = ensure_report_header(
            text,
            fetch_result.week_start,
            fetch_result.week_end,
        )
        return text

    def ping(self, prompt: str = PING_PROMPT) -> str:
        """连通性测活：发一条短提示词，返回模型原文回复。"""
        logger.info(
            "LLM 测活: model=%s, base_url=%s, prompt=%s",
            self.settings.llm_model,
            self.settings.llm_base_url,
            prompt,
        )
        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=64,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM 返回空内容")
        return content

    def summarize(self, fetch_result: FetchResult) -> str:
        """根据提交结果生成周报正文。"""
        if fetch_result.total_commits == 0:
            logger.info("本周无提交，跳过 LLM 调用")
            return ensure_report_header(
                "本周暂无提交记录",
                fetch_result.week_start,
                fetch_result.week_end,
            )

        user_prompt = self.build_user_prompt(fetch_result)
        logger.info(
            "调用 LLM 生成周报: model=%s, base_url=%s, commits=%s",
            self.settings.llm_model,
            self.settings.llm_base_url,
            fetch_result.total_commits,
        )

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("LLM 返回空内容")
        return self.postprocess(content, fetch_result)
