
package com.example.aicoach.service;

import com.example.aicoach.dto.DailyPlanRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.dto.TaskDto;
import com.example.aicoach.entity.DailyPlan;
import com.example.aicoach.entity.Task;
import com.example.aicoach.feign.AiServiceClient;
import com.example.aicoach.repository.DailyPlanRepository;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Slf4j
@RequiredArgsConstructor
public class PlanService {

    private final AiServiceClient aiServiceClient;
    private final DailyPlanRepository dailyPlanRepository;

    /**
     * 获取今日计划。优先从缓存/数据库获取，否则通过AI服务生成。
     * @param goal 今天的学习目标
     * @return 每日计划响应
     */
    @Cacheable(value = "dailyPlan", key = "T(java.time.LocalDate).now().toString()")
    @CircuitBreaker(name = "ai-service", fallbackMethod = "getDailyPlanFallback")
    @Transactional
    public DailyPlanResponse getTodayPlan(String goal) {
        LocalDate today = LocalDate.now();
        // 尝试从数据库查找今天的计划，因为缓存可能在前一天就已写入
        return dailyPlanRepository.findByPlanDate(today)
                .map(this::convertToDto)
                .map(plan -> {
                    log.info("从数据库中获取到今天的计划。");
                    return plan;
                })
                .orElseGet(() -> {
                    log.info("数据库中没有今天的计划，调用AI服务生成新计划。");
                    DailyPlanResponse newPlanDto = aiServiceClient.getDailyPlan(new DailyPlanRequest(goal));
                    savePlan(newPlanDto, today);
                    return newPlanDto;
                });
    }

    /**
     * 熔断降级方法。当ai-service不可用时，返回一个预设的默认计划。
     * @param goal 原始请求的目标
     * @param t 触发熔断的异常
     * @return 一个默认的、静态的每日计划
     */
    public DailyPlanResponse getDailyPlanFallback(String goal, Throwable t) {
        log.warn("AI服务调用失败或超时，启动熔断降级。错误: {}", t.getMessage());
        DailyPlanResponse fallbackResponse = new DailyPlanResponse();
        fallbackResponse.setPlanTitle("默认学习计划 (服务降级)");
        
        TaskDto task = new TaskDto();
        task.setTaskId(1);
        task.setDescription("AI服务当前不可用。请先复习Java基础知识，例如集合框架和多线程。");
        task.setEstimatedTime("2-3 小时");
        task.setStatus("待开始");
        
        fallbackResponse.setTasks(Collections.singletonList(task));
        return fallbackResponse;
    }
    
    private void savePlan(DailyPlanResponse dto, LocalDate date) {
        DailyPlan plan = new DailyPlan();
        plan.setPlanTitle(dto.getPlanTitle());
        plan.setPlanDate(date);
        
        List<Task> tasks = dto.getTasks().stream().map(taskDto -> {
            Task task = new Task();
            task.setTaskId(taskDto.getTaskId());
            task.setDescription(taskDto.getDescription());
            task.setEstimatedTime(taskDto.getEstimatedTime());
            task.setStatus(taskDto.getStatus());
            // 建立双向关联
            task.setDailyPlan(plan);
            return task;
        }).collect(Collectors.toList());
        
        plan.setTasks(tasks);
        dailyPlanRepository.save(plan);
        log.info("已将 {} 的新计划保存至数据库。", date);
    }

    private DailyPlanResponse convertToDto(DailyPlan plan) {
        DailyPlanResponse dto = new DailyPlanResponse();
        dto.setPlanTitle(plan.getPlanTitle());
        List<TaskDto> taskDtos = plan.getTasks().stream().map(task -> {
            TaskDto taskDto = new TaskDto();
            taskDto.setTaskId(task.getTaskId());
            taskDto.setDescription(task.getDescription());
            taskDto.setEstimatedTime(task.getEstimatedTime());
            taskDto.setStatus(task.getStatus());
            return taskDto;
        }).collect(Collectors.toList());
        dto.setTasks(taskDtos);
        return dto;
    }
}
