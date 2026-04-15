
from langchain.agents import AgentExecutor, create_openai_tools_agent

from ..tools.local_tools import get_current_time, search_my_notes
from ..tools.mcp_adapter import get_mcp_tools
from ..core.llm import llm
from ..prompts.templates import PLANNER_AGENT_PROMPT_TEMPLATE
from ..core.config import settings

_agent_executor = None

def get_planner_agent_executor() -> AgentExecutor:
    """
    构建并返回每日计划 Agent 的执行器 (单例模式)。

    这个 Agent 被赋予了多个工具，并被指示如何思考和行动来为用户创建每日计划。
    技术要点：
    1.  **Agent + Tool Calling**: 使用 `create_openai_tools_agent` 创建一个能够进行工具调用的 Agent。
    2.  **多工具集成**: 集成了 `get_current_time`, `search_my_notes` 和一个模拟的 MCP 工具。
    3.  **AgentExecutor**: 负责运行 Agent 的思考-行动-观察循环，`verbose=True` 会打印出详细过程。

    Returns:
        AgentExecutor: 配置好的 Agent 执行器实例。
    """
    global _agent_executor
    if _agent_executor is None:
        print("Initializing planner agent...")
        # 1. 收集所有可用的工具
        tools = [get_current_time, search_my_notes]
        tools.extend(get_mcp_tools()) # 添加来自 MCP 的模拟工具
        print(f"Planner agent initialized with {len(tools)} tools.")
        
        # 2. 创建 Agent
        # 使用 `create_openai_tools_agent` 来创建一个能理解并使用 OpenAI 工具调用格式的 Agent
        agent = create_openai_tools_agent(llm, tools, PLANNER_AGENT_PROMPT_TEMPLATE)
        
        # 3. 创建 Agent 执行器
        # `AgentExecutor` 负责运行 Agent，并处理其思考-行动-观察的循环
        _agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=settings.AGENT_VERBOSE, # 打印详细的思考过程
            handle_parsing_errors=True, # 增加对解析错误的鲁棒性
            return_intermediate_steps=False # 通常在生产中关闭，以简化输出
        )
        print("Planner agent executor created.")
    
    return _agent_executor

