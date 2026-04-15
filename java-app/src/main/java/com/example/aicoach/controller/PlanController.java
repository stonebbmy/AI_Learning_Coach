
package com.example.aicoach.controller;

import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.service.PlanService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/plan")
@RequiredArgsConstructor
@Tag(name = "3. Daily Plan", description = "每日学习计划管理")
public class PlanController {

    private final PlanService planService;

    @GetMapping("/today")
    @Operation(summary = "获取今日学习计划", 
               description = "内部调用 Python AI 服务生成或从缓存/数据库获取今日计划。体现了OpenFeign、Resilience4j熔断和Spring Cache缓存。")
    public DailyPlanResponse getTodaysPlan(
            @Parameter(description = "今天的核心学习目标", example = "学习并实践 Spring AI 的用法") 
            @RequestParam String goal) {
        return planService.getTodayPlan(goal);
    }
}
