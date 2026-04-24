package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * 智能私教对话请求 DTO。
 * 对应 Python TutorRequest schema。
 */
@Data
public class TutorChatRequest {

    /** 用户的自然语言输入 */
    private String question;

    /** 会话 ID（多轮记忆） */
    @JsonProperty("session_id")
    private String sessionId = "tutor_default";

    /** 用户 ID（由 Java BFF 注入，前端不需传） */
    @JsonProperty("user_id")
    private String userId;
}
