
package com.example.aicoach.controller;

import com.example.aicoach.dto.OutlineConfirmationRequest;
import com.example.aicoach.dto.StudyChapterDto;
import com.example.aicoach.entity.StudyChapter;
import com.example.aicoach.entity.StudyOutline;
import com.example.aicoach.repository.StudyOutlineRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/outline")
@RequiredArgsConstructor
@Tag(name = "2. Study Outline", description = "学习大纲管理")
public class OutlineController {

    private final StudyOutlineRepository outlineRepository;

    @PostMapping("/confirm")
    @Transactional
    @Operation(summary = "确认并持久化学习大纲", description = "接收由AI生成、经用户确认的学习大纲，并将其保存到数据库中。")
    public ResponseEntity<StudyOutline> confirmOutline(@RequestBody OutlineConfirmationRequest request) {
        StudyOutline outline = convertToEntity(request);
        StudyOutline savedOutline = outlineRepository.save(outline);
        return ResponseEntity.ok(savedOutline);
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
