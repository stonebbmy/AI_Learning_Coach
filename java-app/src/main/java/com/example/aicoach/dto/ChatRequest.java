
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 调用 Python AI 服务进行聊天的请求体 DTO。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ChatRequest {
    private String question;
    @JsonProperty("session_id")          // 序列化时字段名为 session_id
    @JsonAlias({"sessionId", "session_id"})  // 反序列化时接受两种名称
    private String sessionId;
}
