
package com.example.aicoach.controller;

import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.filter.UserContextHolder;
import com.example.aicoach.service.PlanService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/plan")
@RequiredArgsConstructor
@Tag(name = "3. Daily Plan", description = "每日学习计划管理")
public class PlanController {

    private final PlanService planService;

    @GetMapping("/today")
    @Operation(summary = "获取今日学习计划",
               description = "若传入 outlineId，则自动从已确认大纲中提取章节注入计划生成，形成 Outline→Plan 数据流。")
    public DailyPlanResponse getTodaysPlan(
            @Parameter(description = "今天的核心学习目标", example = "学习并实践 Spring AI 的用法")
            @RequestParam String goal,
            @Parameter(description = "可选：已确认大纲的数据库 ID，用于约束计划生成范围")
            @RequestParam(required = false) Long outlineId) {
        String userId = UserContextHolder.get();
        return planService.getTodayPlan(goal, userId, outlineId);
    }
}
