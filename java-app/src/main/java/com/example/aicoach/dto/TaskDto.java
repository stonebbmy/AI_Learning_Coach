
package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * 每日计划中单个任务的数据传输对象 (DTO)。
 */
@Data
public class TaskDto {
    /** 任务在数据库中的主键 ID（用于状态更新接口） */
    private Long id;

    @JsonProperty("task_id")
    private int taskId;

    private String description;

    @JsonProperty("estimated_time")
    private String estimatedTime;

    private String status;
}
