package com.example.aicoach.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * 与 Python {@code StudyOutlineResponse} JSON 一致（snake_case 由 Jackson 通过 @JsonProperty 读写）。
 * 经 BFF 转给前端，与 {@code web} 中 OutlineGenerateResponse 一致。
 */
@Data
public class OutlineGenerateAiResponse {
    private String title;
    private String overview;
    private List<OutlineGenerateChapterItem> chapters;

    @Data
    public static class OutlineGenerateChapterItem {
        @JsonProperty("chapter_title")
        private String chapterTitle;
        private String description;
        @JsonProperty("key_points")
        private List<String> keyPoints;
    }
}
