package com.example.aicoach.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 多轮对话中的一条消息（与 Python ChatMessage 对齐）。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ChatMessageDto {
    private String role;
    private String content;
}
