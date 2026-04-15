
package com.example.aicoach.dto;

import lombok.Data;

/**
 * 每日计划中单个任务的数据传输对象 (DTO)。
 */
@Data
public class TaskDto {
    private int taskId;
    private String description;
    private String estimatedTime;
    private String status;
}
