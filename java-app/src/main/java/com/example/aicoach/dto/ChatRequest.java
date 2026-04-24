
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 调用 Python AI 服务进行聊天的请求体 DTO。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ChatRequest {
    private String question;

    @JsonProperty("session_id")
    @JsonAlias({"sessionId", "session_id"})
    private String sessionId;

    /** 可选：显式携带近期多轮消息；为空时由 Python 端按 session_id 从 Redis 读取 */
    private List<ChatMessageDto> messages;

    /** 可选：前端传入的每日计划数据库 ID，用于注入今日任务上下文 */
    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private Long planId;

    /** 由 Java 层从 DailyPlan 数据库记录生成，注入 Python 的 plan_context 字段 */
    @JsonProperty("plan_context")
    private String planContext;

    @JsonProperty("user_id")
    private String userId;
}
