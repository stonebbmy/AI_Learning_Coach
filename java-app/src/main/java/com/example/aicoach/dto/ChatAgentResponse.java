package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * Python /api/chat/agent 的 JSON 响应。
 */
@Data
public class ChatAgentResponse {
    private String answer;
    @JsonProperty("session_id")
    private String sessionId;
    @JsonProperty("request_id")
    private String requestId;
}
