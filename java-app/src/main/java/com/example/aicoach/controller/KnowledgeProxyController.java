
package com.example.aicoach.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.io.IOException;

/**
 * 知识库操作代理：将前端 /api/knowledge/* 请求透传至 ai-service，
 * 统一走 Java BFF 层，前端无需直连 Python。
 */
@RestController
@RequestMapping("/api/knowledge")
@Slf4j
@Tag(name = "1. Knowledge", description = "知识库管理（代理到 ai-service）")
public class KnowledgeProxyController {

    private final WebClient webClient;

    public KnowledgeProxyController(@Value("${ai-service.url}") String aiServiceUrl) {
        this.webClient = WebClient.builder().baseUrl(aiServiceUrl).build();
    }

    @GetMapping("/summary")
    @Operation(summary = "知识库概览（代理）")
    public Mono<ResponseEntity<String>> summary(
            @RequestParam(required = false, defaultValue = "anonymous") String user_id) {
        return webClient.get()
                .uri(u -> u.path("/knowledge/summary").queryParam("user_id", user_id).build())
                .retrieve()
                .toEntity(String.class);
    }

    @GetMapping("/chunks")
    @Operation(summary = "分页浏览向量块（代理）")
    public Mono<ResponseEntity<String>> chunks(
            @RequestParam(required = false) String source,
            @RequestParam(required = false, defaultValue = "anonymous") String user_id,
            @RequestParam(required = false, defaultValue = "30") int limit,
            @RequestParam(required = false, defaultValue = "0") int offset) {
        return webClient.get()
                .uri(u -> {
                    var b = u.path("/knowledge/chunks")
                            .queryParam("user_id", user_id)
                            .queryParam("limit", limit)
                            .queryParam("offset", offset);
                    if (source != null) b.queryParam("source", source);
                    return b.build();
                })
                .retrieve()
                .toEntity(String.class);
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "上传 Markdown 笔记到向量库（代理）")
    public Mono<ResponseEntity<String>> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false, defaultValue = "anonymous") String user_id) throws IOException {
        byte[] bytes = file.getBytes();
        String filename = file.getOriginalFilename();

        ByteArrayResource resource = new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        };

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        HttpHeaders fileHeaders = new HttpHeaders();
        fileHeaders.setContentType(MediaType.TEXT_PLAIN);
        fileHeaders.setContentDispositionFormData("file", filename);
        body.add("file", new org.springframework.http.HttpEntity<>(resource, fileHeaders));

        return webClient.post()
                .uri(u -> u.path("/knowledge/upload").queryParam("user_id", user_id).build())
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(body))
                .retrieve()
                .toEntity(String.class);
    }
}
