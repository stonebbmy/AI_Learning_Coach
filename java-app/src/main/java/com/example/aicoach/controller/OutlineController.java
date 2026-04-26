
package com.example.aicoach.controller;

import com.example.aicoach.dto.OutlineConfirmationRequest;
import com.example.aicoach.dto.OutlineGenerateAiResponse;
import com.example.aicoach.dto.OutlineGenerateRequestDto;
import com.example.aicoach.dto.StudyChapterDto;
import com.example.aicoach.entity.StudyChapter;
import com.example.aicoach.entity.StudyOutline;
import com.example.aicoach.filter.UserContextHolder;
import com.example.aicoach.repository.StudyOutlineRepository;
import com.example.aicoach.service.OutlineService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/outline")
@Tag(name = "2. Study Outline", description = "学习大纲管理")
public class OutlineController {

    private final StudyOutlineRepository outlineRepository;
    private final OutlineService outlineService;
    private final WebClient aiServiceWebClient;

    public OutlineController(StudyOutlineRepository outlineRepository,
                             OutlineService outlineService,
                             @Value("${ai-service.url}") String aiServiceUrl) {
        this.outlineRepository = outlineRepository;
        this.outlineService = outlineService;
        this.aiServiceWebClient = WebClient.builder().baseUrl(aiServiceUrl).build();
    }

    @PostMapping(value = "/generate", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    @Operation(summary = "AI 生成学习大纲（经 BFF 代理至 ai-service）",
               description = "转发至 Python /api/outline/generate，与知识库/聊天等接口一致统一走 Java 入口。")
    public Mono<ResponseEntity<OutlineGenerateAiResponse>> generateOutline(@RequestBody OutlineGenerateRequestDto request) {
        return aiServiceWebClient.post()
                .uri("/outline/generate")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .toEntity(OutlineGenerateAiResponse.class)
                .map(entity -> ResponseEntity.status(entity.getStatusCode()).body(entity.getBody()));
    }

    @PostMapping("/confirm")
    @Transactional
    @Operation(summary = "确认并持久化学习大纲",
               description = "接收由 AI 生成、经用户确认的学习大纲，保存到数据库后返回包含 id 的实体，供前端关联后续计划生成。")
    public ResponseEntity<StudyOutline> confirmOutline(@RequestBody OutlineConfirmationRequest request) {
        StudyOutline outline = convertToEntity(request);
        outline.setUserId(UserContextHolder.get());
        StudyOutline savedOutline = outlineRepository.save(outline);
        return ResponseEntity.ok(savedOutline);
    }

    @GetMapping("/list")
    @Operation(summary = "查询当前用户已确认的大纲列表")
    public ResponseEntity<List<StudyOutline>> listOutlines() {
        String userId = UserContextHolder.get();
        List<StudyOutline> outlines = outlineRepository.findAll().stream()
                .filter(o -> userId.equals(o.getUserId()))
                .collect(Collectors.toList());
        return ResponseEntity.ok(outlines);
    }

    @DeleteMapping("/{id}")
    @Transactional
    @Operation(summary = "删除已保存的大纲", description = "仅本人可删；历史日计划的 source_outline_id 会置为 null，不删历史任务行。")
    public ResponseEntity<Void> deleteOutline(@PathVariable Long id) {
        outlineService.deleteOutlineForUser(id, UserContextHolder.get());
        return ResponseEntity.noContent().build();
    }

    private StudyOutline convertToEntity(OutlineConfirmationRequest dto) {
        StudyOutline outline = new StudyOutline();
        outline.setTitle(dto.getTitle());
        outline.setOverview(dto.getOverview());

        List<StudyChapter> chapters = dto.getChapters().stream()
                .map(this::convertChapterDtoToEntity)
                .collect(Collectors.toList());

        outline.setChapters(chapters);
        return outline;
    }

    private StudyChapter convertChapterDtoToEntity(StudyChapterDto dto) {
        StudyChapter chapter = new StudyChapter();
        chapter.setChapterTitle(dto.getChapterTitle());
        chapter.setDescription(dto.getDescription());
        chapter.setKeyPoints(dto.getKeyPoints());
        return chapter;
    }
}
