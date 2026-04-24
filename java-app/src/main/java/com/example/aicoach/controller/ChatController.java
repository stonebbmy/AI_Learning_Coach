
package com.example.aicoach.controller;

import com.example.aicoach.dto.ChatAgentResponse;
import com.example.aicoach.dto.ChatRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import com.example.aicoach.dto.TaskDto;
import com.example.aicoach.entity.DailyPlan;
import com.example.aicoach.feign.AiServiceClient;
import com.example.aicoach.filter.UserContextHolder;
import com.example.aicoach.repository.DailyPlanRepository;
import com.example.aicoach.service.ChatService;
import com.example.aicoach.service.PlanService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "4. Chat", description = "与 AI 学习助理进行问答")
public class ChatController {

    private final ChatService chatService;
    private final AiServiceClient aiServiceClient;
    private final DailyPlanRepository dailyPlanRepository;
    private final PlanService planService;

    @PostMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "流式问答接口（RAG + Plan 上下文注入）",
               description = "若请求携带 planId，从数据库查今日计划并注入 plan_context，实现 Plan→Chat 数据流。")
    public Flux<String> chat(@RequestBody ChatRequest request) {
        String userId = UserContextHolder.get();
        request.setUserId(userId);

        if (request.getPlanId() != null && (request.getPlanContext() == null || request.getPlanContext().isBlank())) {
            dailyPlanRepository.findById(request.getPlanId()).ifPresent(plan -> {
                String ctx = buildPlanContext(plan);
                request.setPlanContext(ctx);
                log.info("已为 session={} 注入 planId={} 的计划上下文", request.getSessionId(), request.getPlanId());
            });
        }

        return chatService.streamChat(request);
    }

    @PostMapping(value = "/agent", produces = MediaType.APPLICATION_JSON_VALUE)
    @Operation(summary = "工具调用 Agent（非流式）", description = "转发到 Python /api/chat/agent，演示 Function Calling / ReAct。")
    public ResponseEntity<ChatAgentResponse> chatAgent(@RequestBody ChatRequest request) {
        request.setUserId(UserContextHolder.get());
        return ResponseEntity.ok(aiServiceClient.chatAgent(request));
    }

    @PostMapping("/history")
    @Operation(summary = "保存完整对话记录",
               description = "客户端在 SSE 流结束后调用，将完整问答落库（PostgreSQL ChatHistory 表）。")
    public ResponseEntity<Void> saveHistory(
            @RequestParam String sessionId,
            @RequestParam String question,
            @RequestBody(required = false) String answer) {
        chatService.saveChatHistory(sessionId, question, answer != null ? answer : "", UserContextHolder.get());
        return ResponseEntity.ok().build();
    }

    @PostMapping("/vision-probe")
    @Operation(summary = "多模态占位探测（代理到 Python）")
    public ResponseEntity<Object> visionProbe(@RequestBody Object body) {
        return ResponseEntity.status(503).body(java.util.Map.of("message", "视觉能力暂未开放"));
    }

    private String buildPlanContext(DailyPlan plan) {
        StringBuilder sb = new StringBuilder();
        sb.append("【今日学习计划：").append(plan.getPlanTitle()).append("】\n");
        if (plan.getTasks() != null) {
            plan.getTasks().forEach(task ->
                sb.append("- ").append(task.getDescription())
                  .append("（预计 ").append(task.getEstimatedTime()).append("，状态：").append(task.getStatus()).append("）\n")
            );
        }
        return sb.toString().trim();
    }
}
