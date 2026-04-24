package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 私教上下文同步请求 DTO（前端切换大纲/计划时调用）。
 */
@Data
public class TutorContextRequest {

    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("current_outline_id")
    private Integer currentOutlineId;

    @JsonProperty("current_plan_id")
    private Integer currentPlanId;

    @JsonProperty("active_topic")
    private String activeTopic = "";

    @JsonProperty("progress_rate")
    private double progressRate = 0.0;

    @JsonProperty("outline_chapters")
    private List<String> outlineChapters;

    @JsonProperty("plan_tasks")
    private List<Map<String, Object>> planTasks;
}
