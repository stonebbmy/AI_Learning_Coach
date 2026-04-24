
package com.example.aicoach.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

/**
 * 健康检查代理：将 /api/health/detail 透传至 ai-service。
 */
@RestController
@RequestMapping("/api/health")
@Tag(name = "0. Health", description = "服务健康状态")
public class HealthProxyController {

    private final WebClient webClient;

    public HealthProxyController(@Value("${ai-service.url}") String aiServiceUrl) {
        this.webClient = WebClient.builder().baseUrl(aiServiceUrl).build();
    }

    @GetMapping("/detail")
    @Operation(summary = "AI 服务详细健康状态（代理）")
    public Mono<ResponseEntity<String>> detail() {
        return webClient.get().uri("/health/detail").retrieve().toEntity(String.class);
    }
}
