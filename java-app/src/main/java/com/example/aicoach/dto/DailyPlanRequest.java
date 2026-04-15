
package com.example.aicoach.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 调用 Python AI 服务生成每日计划的请求体 DTO。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class DailyPlanRequest {
    private String goal;
}
