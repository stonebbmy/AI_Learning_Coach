
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
    /** 计划在 Java 数据库中的 ID，前端用于关联聊天上下文 */
    private Long id;

    @JsonProperty("plan_title")
    private String planTitle;

    private List<TaskDto> tasks;
}
