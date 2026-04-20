
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
    @JsonProperty("session_id")          // 序列化时字段名为 session_id
    @JsonAlias({"sessionId", "session_id"})  // 反序列化时接受两种名称
    private String sessionId;
    /** 可选：显式携带近期多轮消息；为空时由 Python 端按 session_id 从 Redis 读取 */
    private List<ChatMessageDto> messages;
}
