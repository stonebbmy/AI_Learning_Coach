
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * 每日计划中单个任务的数据传输对象 (DTO)。
 */
@Data
public class TaskDto {
    @JsonProperty("task_id")
    private int taskId;
    private String description;
    @JsonProperty("estimated_time")
    private String estimatedTime;
    private String status;
}
