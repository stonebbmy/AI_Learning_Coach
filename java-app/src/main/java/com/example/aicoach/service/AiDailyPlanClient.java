package com.example.aicoach.service;

import com.example.aicoach.dto.DailyPlanRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.dto.TaskDto;
import com.example.aicoach.feign.AiServiceClient;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Collections;

/**
 * 仅对 Feign 调 AI 包熔断，与业务异常（如 {@code NoTodayPlanException}）解耦。
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class AiDailyPlanClient {

    private final AiServiceClient aiServiceClient;

    @CircuitBreaker(name = "ai-service", fallbackMethod = "getDailyPlanFallback")
    public DailyPlanResponse getDailyPlan(DailyPlanRequest req) {
        return aiServiceClient.getDailyPlan(req);
    }

    @SuppressWarnings("unused")
    public DailyPlanResponse getDailyPlanFallback(DailyPlanRequest req, Throwable t) {
        log.warn("AI 服务调用失败或超时，启动熔断降级。错误: {}", t.getMessage());
        DailyPlanResponse fallbackResponse = new DailyPlanResponse();
        fallbackResponse.setPlanTitle("默认学习计划 (服务降级)");
        fallbackResponse.setSourceOutlineId(null);
        String g = req.getGoal() != null ? req.getGoal() : "";
        fallbackResponse.setSourceGoal(g);

        TaskDto task = new TaskDto();
        task.setTaskId(1);
        task.setDescription("AI 服务当前不可用。请先复习 Java 基础知识，例如集合框架和多线程。");
        task.setEstimatedTime("2-3 小时");
        task.setStatus("待开始");
        fallbackResponse.setTasks(Collections.singletonList(task));
        return fallbackResponse;
    }
}
