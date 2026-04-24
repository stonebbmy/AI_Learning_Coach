
package com.example.aicoach.service;

import com.example.aicoach.dto.DailyPlanRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.dto.TaskDto;
import com.example.aicoach.entity.DailyPlan;
import com.example.aicoach.entity.StudyChapter;
import com.example.aicoach.entity.StudyOutline;
import com.example.aicoach.entity.Task;
import com.example.aicoach.feign.AiServiceClient;
import com.example.aicoach.repository.DailyPlanRepository;
import com.example.aicoach.repository.StudyOutlineRepository;
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
    private final StudyOutlineRepository studyOutlineRepository;

    /**
     * 获取今日计划。优先从缓存/数据库获取，否则通过 AI 服务生成。
     * 若传入 outlineId，则从数据库读取大纲章节并注入计划请求，实现 Outline→Plan 数据流。
     *
     * @param goal      今天的学习目标
     * @param userId    用户 ID（来自 UserContextHolder）
     * @param outlineId 可选：已确认大纲的 ID
     */
    @Cacheable(value = "dailyPlan", key = "#userId + ':' + T(java.time.LocalDate).now().toString()")
    @CircuitBreaker(name = "ai-service", fallbackMethod = "getDailyPlanFallback")
    @Transactional
    public DailyPlanResponse getTodayPlan(String goal, String userId, Long outlineId) {
        LocalDate today = LocalDate.now();

        return dailyPlanRepository.findByPlanDateAndUserId(today, userId)
                .map(plan -> {
                    log.info("从数据库中获取到 userId={} 今天的计划。", userId);
                    return convertToDto(plan);
                })
                .orElseGet(() -> {
                    log.info("数据库中没有 userId={} 今天的计划，调用 AI 服务生成新计划。", userId);
                    List<String> chapters = resolveChapters(outlineId);
                    DailyPlanRequest req = new DailyPlanRequest(goal, userId, chapters.isEmpty() ? null : chapters);
                    DailyPlanResponse newPlanDto = aiServiceClient.getDailyPlan(req);
                    DailyPlan savedPlan = savePlan(newPlanDto, today, userId);
                    return convertToDto(savedPlan);
                });
    }

    /**
     * 从已确认大纲中提取章节标题列表，注入计划生成请求。
     * 若 outlineId 为 null 或大纲不存在，返回空列表，计划生成不受章节约束。
     */
    private List<String> resolveChapters(Long outlineId) {
        if (outlineId == null) return Collections.emptyList();
        return studyOutlineRepository.findById(outlineId)
                .map(StudyOutline::getChapters)
                .orElse(Collections.emptyList())
                .stream()
                .map(StudyChapter::getChapterTitle)
                .collect(Collectors.toList());
    }

    public DailyPlanResponse getDailyPlanFallback(String goal, String userId, Long outlineId, Throwable t) {
        log.warn("AI 服务调用失败或超时，启动熔断降级。错误: {}", t.getMessage());
        DailyPlanResponse fallbackResponse = new DailyPlanResponse();
        fallbackResponse.setPlanTitle("默认学习计划 (服务降级)");

        TaskDto task = new TaskDto();
        task.setTaskId(1);
        task.setDescription("AI 服务当前不可用。请先复习 Java 基础知识，例如集合框架和多线程。");
        task.setEstimatedTime("2-3 小时");
        task.setStatus("待开始");

        fallbackResponse.setTasks(Collections.singletonList(task));
        return fallbackResponse;
    }

    private DailyPlan savePlan(DailyPlanResponse dto, LocalDate date, String userId) {
        DailyPlan plan = new DailyPlan();
        plan.setPlanTitle(dto.getPlanTitle());
        plan.setPlanDate(date);
        plan.setUserId(userId);

        List<Task> tasks = dto.getTasks().stream().map(taskDto -> {
            Task task = new Task();
            task.setTaskId(taskDto.getTaskId());
            task.setDescription(taskDto.getDescription());
            task.setEstimatedTime(taskDto.getEstimatedTime());
            task.setStatus(taskDto.getStatus() != null ? taskDto.getStatus() : "待开始");
            task.setDailyPlan(plan);
            return task;
        }).collect(Collectors.toList());

        plan.setTasks(tasks);
        DailyPlan saved = dailyPlanRepository.save(plan);
        log.info("已将 {} 用户 {} 的新计划保存至数据库，id={}。", date, userId, saved.getId());
        return saved;
    }

    public DailyPlanResponse convertToDto(DailyPlan plan) {
        DailyPlanResponse dto = new DailyPlanResponse();
        dto.setId(plan.getId());
        dto.setPlanTitle(plan.getPlanTitle());
        List<TaskDto> taskDtos = plan.getTasks().stream().map(task -> {
            TaskDto taskDto = new TaskDto();
            taskDto.setId(task.getId());
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
