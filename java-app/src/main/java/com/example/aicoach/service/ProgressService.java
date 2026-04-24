
package com.example.aicoach.service;

import com.example.aicoach.entity.DailyPlan;
import com.example.aicoach.entity.Task;
import com.example.aicoach.repository.DailyPlanRepository;
import com.example.aicoach.repository.TaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@Slf4j
@RequiredArgsConstructor
public class ProgressService {

    private final TaskRepository taskRepository;
    private final DailyPlanRepository dailyPlanRepository;

    /**
     * 更新任务状态。若状态改为"已完成"，则记录完成时间。
     */
    @Transactional
    public Task updateTaskStatus(Long taskId, String newStatus) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new NoSuchElementException("任务 ID " + taskId + " 不存在"));
        task.setStatus(newStatus);
        if ("已完成".equals(newStatus) || "DONE".equalsIgnoreCase(newStatus)) {
            task.setCompletedAt(LocalDateTime.now());
        } else {
            task.setCompletedAt(null);
        }
        Task saved = taskRepository.save(task);
        log.info("任务 id={} 状态更新为 '{}'", taskId, newStatus);
        return saved;
    }

    /**
     * 统计指定用户的学习进度汇总。
     * 按计划分组，聚合各计划中的任务完成情况。
     */
    @Transactional(readOnly = true)
    public Map<String, Object> getProgressSummary(String userId) {
        List<DailyPlan> plans = dailyPlanRepository.findByUserIdOrderByPlanDateDesc(userId);

        int totalTasks = 0;
        int doneTasks = 0;
        List<Map<String, Object>> dailyStats = new ArrayList<>();

        for (DailyPlan plan : plans) {
            List<Task> tasks = plan.getTasks();
            int planTotal = tasks.size();
            int planDone = (int) tasks.stream()
                    .filter(t -> "已完成".equals(t.getStatus()) || "DONE".equalsIgnoreCase(t.getStatus()))
                    .count();
            totalTasks += planTotal;
            doneTasks += planDone;

            Map<String, Object> stat = new LinkedHashMap<>();
            stat.put("planDate", plan.getPlanDate().toString());
            stat.put("planTitle", plan.getPlanTitle());
            stat.put("total", planTotal);
            stat.put("done", planDone);
            stat.put("completionRate", planTotal == 0 ? 0.0 : (double) planDone / planTotal);
            dailyStats.add(stat);
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("userId", userId);
        summary.put("totalTasks", totalTasks);
        summary.put("doneTasks", doneTasks);
        summary.put("completionRate", totalTasks == 0 ? 0.0 : (double) doneTasks / totalTasks);
        summary.put("dailyStats", dailyStats);
        return summary;
    }
}
