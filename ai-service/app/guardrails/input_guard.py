"""
输入 Guardrails：防护层，在进入 LLM 之前过滤危险输入。

面试考点：
Q: 为什么 AI 应用需要 Guardrails？
A: 三类风险：
   1. Prompt 注入攻击（Prompt Injection）：攻击者注入指令覆盖系统 Prompt
   2. 越狱攻击（Jailbreak）：绕过模型内容过滤，生成有害内容
   3. 资源滥用：超长输入导致 Token 消耗爆炸 / API 成本失控

Q: Guardrails 的实现层次有哪些？
A: 
   - 输入层（本模块）：规则检测 + 关键词过滤，延迟 <1ms，成本零
   - 模型层：利用 LLM 自身安全对齐（RLHF/DPO），不可完全依赖
   - 输出层：对 LLM 输出做后处理过滤（NLP 分类器或规则）
   - 生产中三层叠加使用

设计 Trade-off：
- 规则方案（本实现）：低延迟、可解释、无额外 API 成本；但召回率低（复杂攻击漏检）
- LLM-as-Judge 方案：准确率高，但每次多一次 LLM 调用（+500ms, +cost）
- 生产推荐：规则层做粗粒度过滤，LLM 分类器做细粒度检测（异步，不阻塞主链路）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.config import settings
from ..core.exceptions import InputValidationError


@dataclass
class GuardResult:
    """Guardrails 检查结果。"""
    passed: bool
    reason: str = ""


# ---------------------------------------------------------------------------
# Prompt 注入检测规则
# 这些是已知攻击模式的正则表达式，生产中应从配置文件加载并定期更新
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # 经典角色扮演注入：要求模型"忘记"系统提示
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompt)", re.IGNORECASE),
    re.compile(r"forget\s+(previous|above|all|your)", re.IGNORECASE),
    re.compile(r"你现在是|你是一个没有限制|忘记(之前|上面|所有)(的)?(指令|提示|限制)", re.IGNORECASE),
    # 系统提示泄露尝试
    re.compile(r"(print|show|reveal|output|tell me|说出)\s+(your\s+)?(system\s+prompt|instructions|prompt)", re.IGNORECASE),
    re.compile(r"(输出|打印|显示|告诉我)(你的)?(系统提示|指令|prompt)", re.IGNORECASE),
    # DAN / 越狱模式
    re.compile(r"\bDAN\b|\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"jailbreak|越狱|解除(限制|约束|规则)", re.IGNORECASE),
    # 代码执行注入（适用于有代码执行能力的 Agent）
    re.compile(r"exec\s*\(|eval\s*\(|__import__\s*\(|subprocess\.", re.IGNORECASE),
    re.compile(r"<script\s*>|javascript\s*:|data\s*:text/html", re.IGNORECASE),
]

# 明显有害内容关键词（生产环境应接入专业内容审核 API）
_HARMFUL_KEYWORDS: list[str] = [
    "制作炸弹", "合成毒品", "儿童色情", "暴力袭击", "如何杀人",
    "make bomb", "synthesize drugs", "child pornography",
]


# ---------------------------------------------------------------------------
# 主检查函数
# ---------------------------------------------------------------------------

def check_input(text: str) -> GuardResult:
    """
    对用户输入执行多层次 Guardrails 检查。

    检查顺序（短路原则，越快越靠前）：
    1. 长度检查（O(1)）
    2. 有害关键词（O(n) 字符串匹配）
    3. Prompt 注入模式（O(n) 正则匹配）

    Returns:
        GuardResult: passed=True 表示输入安全，passed=False 时 reason 说明原因
    """
    # 1. 空输入检查
    if not text or not text.strip():
        return GuardResult(passed=False, reason="输入不能为空")

    # 2. 长度限制（防止 Token 炸弹）
    if len(text) > settings.MAX_INPUT_LENGTH:
        return GuardResult(
            passed=False,
            reason=f"输入过长（{len(text)} 字符），最大允许 {settings.MAX_INPUT_LENGTH} 字符",
        )

    # 3. 有害内容关键词检测
    text_lower = text.lower()
    for keyword in _HARMFUL_KEYWORDS:
        if keyword.lower() in text_lower:
            return GuardResult(passed=False, reason="输入包含不允许的内容")

    # 4. Prompt 注入攻击检测
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return GuardResult(passed=False, reason="检测到潜在的 Prompt 注入攻击")

    # 5. 重复字符攻击检测（如 "aaaa...aaaa" 刷屏）
    if _is_repetitive(text):
        return GuardResult(passed=False, reason="输入内容异常（重复字符攻击）")

    return GuardResult(passed=True)


def enforce_input(text: str) -> str:
    """
    检查输入并在不通过时抛出 InputValidationError。
    在 API 路由中调用，方便链式使用：text = enforce_input(request.question)
    """
    result = check_input(text)
    if not result.passed:
        raise InputValidationError(result.reason)
    return text.strip()


def _is_repetitive(text: str, threshold: float = 0.7, min_length: int = 50) -> bool:
    """
    检测文本是否由大量重复字符构成。
    原理：统计最高频字符占比，超过阈值视为异常。
    仅对较长文本生效（短文本误报率高）。
    """
    if len(text) < min_length:
        return False
    from collections import Counter
    char_counts = Counter(text.replace(" ", "").replace("\n", ""))
    if not char_counts:
        return False
    most_common_count = char_counts.most_common(1)[0][1]
    ratio = most_common_count / len(text)
    return ratio > threshold
