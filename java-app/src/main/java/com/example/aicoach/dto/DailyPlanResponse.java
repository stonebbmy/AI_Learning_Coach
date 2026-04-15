
package com.example.aicoach.dto;

import lombok.Data;

import java.util.List;

/**
 * 从 Python AI 服务接收的每日计划响应体 DTO。
 */
@Data
public class DailyPlanResponse {
    private String planTitle;
    private List<TaskDto> tasks;
}
