
package com.example.aicoach.dto;

import lombok.Data;

import java.util.List;

/**
 * 学习章节的数据传输对象 (DTO)。
 */
@Data
public class StudyChapterDto {
    private String chapterTitle;
    private String description;
    private List<String> keyPoints;
}
