
package com.example.aicoach.controller;

import com.example.aicoach.entity.Task;
import com.example.aicoach.filter.UserContextHolder;
import com.example.aicoach.service.ProgressService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequiredArgsConstructor
@Tag(name = "5. Progress", description = "学习进度追踪")
public class ProgressController {

    private final ProgressService progressService;

    @PatchMapping("/api/task/{taskId}/status")
    @Operation(summary = "更新任务完成状态",
               description = "将任务状态更新为：待开始 / 进行中 / 已完成；已完成时自动记录完成时间。")
    public ResponseEntity<Task> updateTaskStatus(
            @PathVariable Long taskId,
            @RequestBody Map<String, String> body) {
        String status = body.getOrDefault("status", "待开始");
        Task updated = progressService.updateTaskStatus(taskId, status);
        return ResponseEntity.ok(updated);
    }

    @GetMapping("/api/progress/summary")
    @Operation(summary = "查询学习进度汇总",
               description = "按日期聚合当前用户的任务完成率，支持在 ProgressView 中展示历史进度曲线。")
    public ResponseEntity<Map<String, Object>> getProgressSummary() {
        String userId = UserContextHolder.get();
        return ResponseEntity.ok(progressService.getProgressSummary(userId));
    }
}
