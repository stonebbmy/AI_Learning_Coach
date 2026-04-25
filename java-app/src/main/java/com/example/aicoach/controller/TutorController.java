package com.example.aicoach.controller;

import com.example.aicoach.dto.TutorChatRequest;
import com.example.aicoach.dto.TutorContextRequest;
import com.example.aicoach.filter.UserContextHolder;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

/**
 * 智能私教总控 API 代理控制器
 *
 * <p>职责：
 * <ol>
 *   <li>注入 userId（从 UserContextHolder 获取，源于 X-User-Id 请求头）</li>
 *   <li>将请求转发到 Python ai-service 的 /api/tutor/chat（SSE）</li>
 *   <li>透明代理 SSE 流，前端直接消费</li>
 * </ol>
 *
 * <p>SSE 事件协议（透传给前端）：
 * <pre>
 *   event: intent, data: LEARN        — 意图分类结果
 *   event: actions, data: ["📚搜索知识库"]  — 执行的工具动作
 *   data: <text chunk>                — 正文流
 *   event: end, data: done            — 流结束
 *   event: error, data: <message>     — 错误（流中断）
 * </pre>
 */
@RestController
@RequestMapping("/api/tutor")
@Slf4j
@Tag(name = "7. Tutor", description = "智能私教总控层（意图理解 + 动态工具调度 + SSE 流式回复）")
public class TutorController {

    private final WebClient webClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public TutorController(
            WebClient.Builder webClientBuilder,
            @Value("${ai-service.url}") String aiServiceUrl) {
        this.webClient = webClientBuilder.baseUrl(aiServiceUrl).build();
    }

    /**
     * 智能私教主对话接口（SSE 流式）。
     *
     * <p>前端发送自然语言，Java BFF 注入 userId 后转发 Python 编排器：
     * 意图分类 → 并行工具调度 → SSE 流式私教回复。
     */
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(
            summary = "智能私教对话（SSE 流式）",
            description = "发送自然语言，AI 自动理解意图，调度工具，流式返回个性化私教回复"
    )
    public Flux<ServerSentEvent<String>> tutorChat(@RequestBody TutorChatRequest request) {
        String userId = UserContextHolder.get();
        request.setUserId(userId);

        if (request.getSessionId() == null || request.getSessionId().isBlank()) {
            request.setSessionId("tutor_" + userId);
        }

        log.info("[Tutor] user={} session={} question='{}'",
                userId, request.getSessionId(),
                request.getQuestion() != null ? request.getQuestion().substring(
                        0, Math.min(50, request.getQuestion().length())) : "");

        // 使用 ServerSentEvent<String> 完整保留 event 字段（intent / actions / card / end / error）。
        // 若用 bodyToFlux(String.class)，Spring 的 SSE 解码器只返回 data 值，event 类型全部丢失，
        // 导致前端永远收不到 event:end，isStreaming 无法重置，Markdown 格式无法渲染。
        return webClient.post()
                .uri("/tutor/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .map(sse -> ServerSentEvent.<String>builder()
                        .event(sse.event())
                        .data(sse.data() != null ? sse.data() : "")
                        .build())
                .doOnError(e -> log.error("[Tutor] stream error user={}: {}", userId, e.getMessage()))
                .doOnComplete(() -> log.info("[Tutor] stream complete user={} session={}", userId, request.getSessionId()));
    }

    /**
     * 更新私教上下文（前端切换大纲或计划时调用）。
     * 将 outlineId / planId / chapters / tasks 写入 Python Redis 缓存，
     * 使后续私教对话能感知当前学习状态。
     */
    @PostMapping("/context")
    @Operation(
            summary = "同步私教上下文",
            description = "前端确认大纲或生成计划后调用，将上下文写入 Redis 供私教使用"
    )
    public Mono<ResponseEntity<Object>> updateContext(@RequestBody TutorContextRequest request) {
        String userId = UserContextHolder.get();
        request.setUserId(userId);
        log.info("[Tutor] updateContext user={} outlineId={} planId={}",
                userId, request.getCurrentOutlineId(), request.getCurrentPlanId());

        return webClient.post()
                .uri("/tutor/context")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> {
                    log.error("[Tutor] updateContext error user={}: {}", userId, e.getMessage());
                    return Mono.just(ResponseEntity.internalServerError()
                            .body((Object) java.util.Map.of("error", "上下文更新失败")));
                });
    }

    /**
     * 获取用户当前私教上下文（调试 / 前端状态初始化）。
     */
    @GetMapping("/context/{userId}")
    @Operation(summary = "获取私教上下文", description = "返回 Redis 中保存的用户学习状态")
    public Mono<ResponseEntity<Object>> getContext(@PathVariable String userId) {
        return webClient.get()
                .uri("/tutor/context/{userId}", userId)
                .retrieve()
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> Mono.just(
                        ResponseEntity.ok((Object) java.util.Map.of("user_id", userId, "context", java.util.Map.of()))
                ));
    }

    /**
     * 获取会话历史记录（前端挂载时用于恢复对话窗口）。
     */
    @GetMapping("/history/{sessionId}")
    @Operation(
            summary = "获取会话历史",
            description = "读取 Redis 中的对话记录，用于前端刷新后恢复聊天界面"
    )
    public Mono<ResponseEntity<Object>> getHistory(
            @PathVariable String sessionId,
            @RequestParam(defaultValue = "20") int limit) {
        log.info("[Tutor] getHistory session={} limit={}", sessionId, limit);
        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/tutor/history/{sessionId}")
                        .queryParam("limit", limit)
                        .build(sessionId))
                .retrieve()
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> {
                    log.error("[Tutor] getHistory error session={}: {}", sessionId, e.getMessage());
                    return Mono.just(ResponseEntity.ok(
                            (Object) java.util.Map.of("session_id", sessionId, "messages", java.util.List.of(), "count", 0)
                    ));
                });
    }
}
