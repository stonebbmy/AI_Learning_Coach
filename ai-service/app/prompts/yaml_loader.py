from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from langchain_core.prompts import ChatPromptTemplate

from ..core.config import settings


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parent


def load_qa_prompt_yaml(version: str | None = None) -> Dict[str, Any]:
    """加载指定版本的 QA Prompt YAML（默认来自 settings.PROMPT_QA_VERSION）。"""
    ver = (version or settings.PROMPT_QA_VERSION).strip().lower()
    path = _prompts_dir() / "versions" / f"qa_{ver}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"QA prompt 版本文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "system" not in data or "human" not in data:
        raise ValueError(f"无效的 QA YAML 结构: {path}")
    return data


def build_qa_chat_template(version: str | None = None) -> ChatPromptTemplate:
    """由 YAML 构建 ChatPromptTemplate（与链式 Runnable 兼容）。"""
    data = load_qa_prompt_yaml(version)
    return ChatPromptTemplate.from_messages(
        [
            ("system", data["system"].strip()),
            ("human", data["human"].strip()),
        ]
    )


def format_history_block(messages: list[dict[str, str]] | None, max_chars: int | None = None) -> str:
    """将多轮消息格式化为注入 system 的 history_block 占位符。"""
    if not messages:
        return ""
    limit = max_chars if max_chars is not None else settings.CHAT_HISTORY_MAX_CHARS
    lines: list[str] = []
    for m in messages:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[-limit:]
        text = "…（历史已截断）\n" + text
    return f"【近期对话摘要（如有）】\n{text}\n" if text else ""
