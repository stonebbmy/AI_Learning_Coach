package com.example.aicoach.service;

import com.example.aicoach.dto.DailyPlanRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.dto.TaskDto;
import com.example.aicoach.entity.DailyPlan;
import com.example.aicoach.entity.StudyChapter;
import com.example.aicoach.entity.StudyOutline;
import com.example.aicoach.entity.Task;
import com.example.aicoach.exception.NoTodayPlanException;
import com.example.aicoach.repository.DailyPlanRepository;
import com.example.aicoach.repository.StudyOutlineRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

@Service
@Slf4j
@RequiredArgsConstructor
public class PlanService {

    private final AiDailyPlanClient aiDailyPlanClient;
    private final DailyPlanRepository dailyPlanRepository;
    private final StudyOutlineRepository studyOutlineRepository;

    /**
     * <ul>
     *   <li>regenerate=true：删当日行后按参数调 AI 生成</li>
     *   <li>regenerate=false 且已有当日行、且请求 goal 为空：直接读档（不调 AI）</li>
     *   <li>regenerate=false 且已有当日行、且 goal 非空：对账一致则直返，否则删后重算</li>
     *   <li>regenerate=false 且无当日行、且 goal 空：抛 {@link NoTodayPlanException}</li>
     *   <li>无当日行、goal 非空：调 AI 并落库</li>
     * </ul>
     */
    @Transactional
    public DailyPlanResponse getTodayPlan(String goal, String userId, Long outlineId, boolean regenerate) {
        LocalDate today = LocalDate.now();
        String normGoal = normalizeGoal(goal);

        if (regenerate) {
            log.info("regenerate=true，删除 userId={} 当日计划后重算", userId);
            deleteTodayPlanIfExists(userId, today);
            return generateAndSave(normGoal, userId, outlineId, today);
        }

        return dailyPlanRepository.findByPlanDateAndUserId(today, userId)
                .map(plan -> {
                    if (normGoal.isEmpty()) {
                        log.info("goal 为空，直返当日计划 userId={} planId={}", userId, plan.getId());
                        return convertToDto(plan);
                    }
                    if (requestMatchesStoredPlan(plan, outlineId, normGoal)) {
                        log.info("今日计划与请求一致，直接返回 userId={} planId={}", userId, plan.getId());
                        return convertToDto(plan);
                    }
                    log.info("今日计划与请求不一致，删除后重新生成 userId={} planId={}", userId, plan.getId());
                    dailyPlanRepository.delete(plan);
                    return generateAndSave(normGoal, userId, outlineId, today);
                })
                .orElseGet(() -> {
                    if (normGoal.isEmpty()) {
                        throw new NoTodayPlanException("今日尚无计划。请先到学习大纲确认/生成大纲，或在此填写目标后生成。");
                    }
                    log.info("数据库中无 userId={} 今日计划，调 AI 生成", userId);
                    return generateAndSave(normGoal, userId, outlineId, today);
                });
    }

    @Transactional
    public void deleteTodayPlanForUser(String userId) {
        deleteTodayPlanIfExists(userId, LocalDate.now());
    }

    private static String normalizeGoal(String goal) {
        if (goal == null) {
            return "";
        }
        return goal.trim();
    }

    private boolean requestMatchesStoredPlan(DailyPlan plan, Long requestOutlineId, String normGoal) {
        if (!Objects.equals(plan.getSourceOutlineId(), requestOutlineId)) {
            return false;
        }
        return normalizeGoal(plan.getSourceGoal()).equals(normGoal);
    }

    private void deleteTodayPlanIfExists(String userId, LocalDate today) {
        dailyPlanRepository.findByPlanDateAndUserId(today, userId)
                .ifPresent(p -> {
                    log.info("删除当日计划 id={} userId={}", p.getId(), userId);
                    dailyPlanRepository.delete(p);
                });
    }

    private DailyPlanResponse generateAndSave(String normGoal, String userId, Long outlineId, LocalDate today) {
        List<String> chapters = resolveChapters(outlineId, userId);
        String goalForAi = normGoal.isEmpty() ? "今日学习" : normGoal;
        DailyPlanRequest req = new DailyPlanRequest(goalForAi, userId, chapters.isEmpty() ? null : chapters);
        DailyPlanResponse newPlanDto = aiDailyPlanClient.getDailyPlan(req);
        DailyPlan saved = savePlan(newPlanDto, today, userId, outlineId, normGoal);
        return convertToDto(saved);
    }

    private List<String> resolveChapters(Long outlineId, String userId) {
        if (outlineId == null) {
            return Collections.emptyList();
        }
        return studyOutlineRepository.findById(outlineId)
                .filter(o -> userId != null && userId.equals(o.getUserId()))
                .map(StudyOutline::getChapters)
                .orElse(Collections.emptyList())
                .stream()
                .map(StudyChapter::getChapterTitle)
                .collect(Collectors.toList());
    }

    private DailyPlan savePlan(DailyPlanResponse dto, LocalDate date, String userId, Long sourceOutlineId, String sourceGoal) {
        DailyPlan plan = new DailyPlan();
        plan.setPlanTitle(dto.getPlanTitle());
        plan.setPlanDate(date);
        plan.setUserId(userId);
        plan.setSourceOutlineId(sourceOutlineId);
        plan.setSourceGoal(sourceGoal);

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
        log.info("已保存 {} 用户 {} 新计划 id={} sourceOutlineId={}", date, userId, saved.getId(), sourceOutlineId);
        return saved;
    }

    public DailyPlanResponse convertToDto(DailyPlan plan) {
        DailyPlanResponse dto = new DailyPlanResponse();
        dto.setId(plan.getId());
        dto.setPlanTitle(plan.getPlanTitle());
        dto.setSourceOutlineId(plan.getSourceOutlineId());
        dto.setSourceGoal(plan.getSourceGoal());
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
