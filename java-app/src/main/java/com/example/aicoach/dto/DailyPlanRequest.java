
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 调用 Python AI 服务生成每日计划的请求体 DTO。
 */
@Data
@NoArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class DailyPlanRequest {
    private String goal;

    @JsonProperty("user_id")
    private String userId;

    /** 可选：来自已确认大纲的章节标题列表，Python 侧据此约束计划范围 */
    private List<String> chapters;

    public DailyPlanRequest(String goal) {
        this.goal = goal;
    }

    public DailyPlanRequest(String goal, String userId, List<String> chapters) {
        this.goal = goal;
        this.userId = userId;
        this.chapters = chapters;
    }
}
