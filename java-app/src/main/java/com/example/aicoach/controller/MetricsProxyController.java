
package com.example.aicoach.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

/**
 * 可观测性指标代理：将前端指标/健康类请求透传至 ai-service，
 * 统一入口，消除前端直连 Python 的安全隐患。
 */
@RestController
@RequestMapping("/api/metrics")
@Tag(name = "7. Metrics", description = "可观测性指标（代理到 ai-service）")
public class MetricsProxyController {

    private final WebClient webClient;

    public MetricsProxyController(@Value("${ai-service.url}") String aiServiceUrl) {
        this.webClient = WebClient.builder().baseUrl(aiServiceUrl).build();
    }

    @GetMapping("/stats")
    @Operation(summary = "综合指标（缓存、Token、延迟，代理）")
    public Mono<ResponseEntity<String>> stats() {
        return webClient.get().uri("/metrics/stats").retrieve().toEntity(String.class);
    }

    @GetMapping("/circuit-breaker")
    @Operation(summary = "LLM 熔断器状态（代理）")
    public Mono<ResponseEntity<String>> circuitBreaker() {
        return webClient.get().uri("/metrics/circuit-breaker").retrieve().toEntity(String.class);
    }

    @GetMapping("/session/{sessionId}")
    @Operation(summary = "会话 Token 用量（代理）")
    public Mono<ResponseEntity<String>> sessionUsage(@PathVariable String sessionId) {
        return webClient.get()
                .uri("/metrics/session/{sid}", sessionId)
                .retrieve()
                .toEntity(String.class);
    }
}

