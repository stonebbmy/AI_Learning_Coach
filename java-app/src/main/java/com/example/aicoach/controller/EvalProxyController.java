
package com.example.aicoach.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

/**
 * RAG 评估代理：将 /api/eval/rag 透传至 ai-service。
 */
@RestController
@RequestMapping("/api/eval")
@Tag(name = "6. Eval", description = "RAG 质量评估（代理到 ai-service）")
public class EvalProxyController {

    private final WebClient webClient;

    public EvalProxyController(@Value("${ai-service.url}") String aiServiceUrl) {
        this.webClient = WebClient.builder().baseUrl(aiServiceUrl).build();
    }

    @PostMapping(value = "/rag", consumes = MediaType.APPLICATION_JSON_VALUE)
    @Operation(summary = "RAG 评估（LLM-as-Judge，代理）")
    public Mono<ResponseEntity<String>> evalRag(@RequestBody Map<String, Object> body) {
        return webClient.post()
                .uri("/eval/rag")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .toEntity(String.class);
    }
}
