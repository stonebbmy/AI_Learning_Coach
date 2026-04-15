
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    FewShotChatMessagePromptTemplate,
)

# ==========================================================================
# 1. 大纲生成 (/outline/generate) 的 Prompt
# ==========================================================================

# --- Few-shot 示例 ---
# 我们提供一个高质量的输入输出对，引导模型按我们期望的格式和深度进行思考。
# 注意：在真实应用中，输出的 value 应该是一个序列化的 JSON 字符串，但为清晰起见，这里用 dict 表示。
# 在代码中，我们会将其转换为字符串。

_FEW_SHOT_OUTPUT_EXAMPLE = '''
{
    "title": "Python开发者2个月快速入门Go语言微服务开发",
    "overview": "本计划旨在帮助有经验的Python开发者在2个月内掌握Go语言核心知识和微服务开发能力。学习路径将重点关注Go的并发特性、标准库以及在云原生领域的应用，最终目标是能够独立构建、测试和部署基于Go的微服务。",
    "chapters": [
        {
            "chapter_title": "第一周：Go基础与环境搭建",
            "description": "熟悉Go语言的基本语法、项目结构和开发工具，为后续学习打下坚实基础。",
            "key_points": [
                "Go的安装与工作区设置 (GOPATH, Go Modules)",
                "基本数据类型、变量、常量",
                "控制流：if/else, for, switch",
                "函数与包（package）的概念",
                "指针（Pointer）的基本使用"
            ]
        },
        {
            "chapter_title": "第二周：Go核心特性：结构体、方法与接口",
            "description": "深入理解Go的面向对象编程范式，掌握接口的核心思想。",
            "key_points": [
                "结构体（Struct）与方法（Method）",
                "接口（Interface）的定义与实现",
                "类型断言与类型转换",
                "组合（Composition）优于继承的思想"
            ]
        },
        {
            "chapter_title": "第三、四周：并发编程",
            "description": "掌握Go语言最核心的并发模型 Goroutine 和 Channel，理解其设计哲学。",
            "key_points": [
                "Goroutine 的创建与使用",
                "Channel 的概念、带缓冲与不带缓冲的 Channel",
                "select 语句实现多路复用",
                "sync 包的使用（Mutex, WaitGroup）",
                "并发模式：生产者-消费者、扇入扇出等"
            ]
        }
    ]
}
'''

few_shot_examples = [
    {
        "input": "我是一个有2年经验的Python后端开发，想在2个月内学习Go语言，目标是能独立开发高性能的微服务。",
        "output": _FEW_SHOT_OUTPUT_EXAMPLE
    }
]

# --- Prompt 模板 ---

# 系统消息模板
# {format_instructions} 将由 LangChain 的 Output Parser 自动填充
outline_system_template = """
你是一个资深的AI学习教练，专注于为用户量身定制技术学习大纲。
你的任务是根据用户提供的【学习目标】和【期望期限】，生成一份详尽、专业、结构化的学习计划。

请严格按照以下格式指令来组织你的输出。确保输出是一个完整的、可以被JSON解析的字符串，不要在JSON代码块前后添加任何额外文本。
{format_instructions}

学习大纲需要满足以下要求：
1.  **逻辑清晰**：章节安排应循序渐进，从基础到进阶。
2.  **内容全面**：覆盖实现学习目标所需的核心技术栈和知识点。
3.  **重点突出**：明确每个章节需要掌握的关键技术点。
4.  **符合实际**：在给定的期限内，计划应该是可行且合理的。
"""

# Few-shot Prompt 模板
# 这个模板将整合系统消息、Few-shot示例和用户输入
# 注意：由于 LangChain 的 FewShotChatMessagePromptTemplate 对于 AI 返回结构化数据（如JSON）的支持不佳，
# 我们将手动在代码中构建 few-shot 消息列表，这里仅作结构展示。
# outline_prompt_template = ... (将在 outline_chain.py 中动态构建)


# ==========================================================================
# 2. 每日计划 Agent (/plan/daily) 的 Prompt
# ==========================================================================

PLANNER_AGENT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", """
你是一个高效的个人学习计划制定助理。
你的任务是根据用户今天的主要目标，结合你可用的工具，为用户生成一份具体的、可执行的任务清单。

你可以使用的工具有：
- `get_current_time`: 获取当前日期和时间，帮助你了解上下文。
- `search_my_notes`: 在用户的个人知识库（学习笔记）中搜索相关信息。如果用户目标是“复习xxx”，这个工具会非常有用。

请遵循以下步骤思考：
1.  **分析目标**：理解用户今天想要完成的核心任务是什么。
2.  **调用工具（可选）**：
    *   如果目标是复习或基于已有知识，思考是否需要 `search_my_notes` 来查找相关笔记，以确定复习的具体内容。
    *   `get_current_time` 可以帮你确认今天的日期。
3.  **制定任务**：将大目标分解为3-5个具体、可操作的小任务。
4.  **估算时间**：为每个任务估算一个合理的时间范围（例如：30-45分钟，1-2小时）。
5.  **格式化输出**：你的最终输出必须是一个符合规范的JSON对象，包含`plan_title`和`tasks`字段，其中`tasks`是一个包含`task_id`, `description`, `estimated_time`的列表。

现在，请开始为用户制定计划。
"""),
        ("human", "我今天的目标是：{goal}"),
        # `placeholder` 是 LangChain Agent 用于插入其思考过程（scratchpad）的地方
        ("placeholder", "{agent_scratchpad}"),
    ]
)


# ==========================================================================
# 3. RAG 问答 (/chat) 的 Prompt
# ==========================================================================

QA_SYSTEM_PROMPT = """
你是一个AI学习助理，专门根据提供的学习笔记内容来回答问题。
你的任务是仅使用下面提供的【学习笔记上下文】来回答用户的【问题】。

请遵循以下规则：
1.  **忠于原文**：你的回答必须完全基于【学习笔记上下文】，不得包含任何外部知识或个人猜测。
2.  **无法回答则坦诚相告**：如果上下文中没有足够的信息来回答问题，请明确告知：“根据我现有的学习笔记，我无法回答这个问题。”
3.  **标注来源**：在回答的末尾，必须清楚地标注信息来源。格式为 `[来自: 文件名]`。如果引用了多个文件，请全部列出。
4.  **语言一致**：请使用与用户【问题】相同的语言进行回答。

---
【学习笔记上下文】
{context}
---
"""

QA_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(QA_SYSTEM_PROMPT),
        HumanMessagePromptTemplate.from_template("【问题】\n{question}"),
    ]
)
