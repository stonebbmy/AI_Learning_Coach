package com.example.aicoach.dto;

import lombok.Data;

/**
 * 与 Python /api/outline/generate 请求体一致：target、deadline。
 */
@Data
public class OutlineGenerateRequestDto {
    private String target;
    private String deadline;
}
