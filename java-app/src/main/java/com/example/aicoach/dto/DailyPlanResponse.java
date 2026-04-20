
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * 从 Python AI 服务接收的每日计划响应体 DTO。
 * Python FastAPI 默认序列化为 snake_case，需显式映射到 Java 字段。
 */
@Data
public class DailyPlanResponse {
    @JsonProperty("plan_title")
    private String planTitle;
    private List<TaskDto> tasks;
}
