
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
            @Parameter(description = "核心学习目标，可空：有当日行时只读；无行且无内容则 404 需先填/去大纲。")
            @RequestParam(required = false, defaultValue = "") String goal,
            @Parameter(description = "可选：已确认大纲的数据库 ID，用于约束计划生成范围")
            @RequestParam(required = false) Long outlineId,
            @Parameter(description = "为 true 时先删除今日计划再按 goal/outline 重新生成")
            @RequestParam(required = false, defaultValue = "false") boolean regenerate) {
        String userId = UserContextHolder.get();
        return planService.getTodayPlan(goal, userId, outlineId, regenerate);
    }

    @DeleteMapping("/today")
    @Operation(summary = "删除当前用户今日计划（及任务，级联）")
    public void deleteToday() {
        planService.deleteTodayPlanForUser(UserContextHolder.get());
    }
}
