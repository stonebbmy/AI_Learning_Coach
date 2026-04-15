
package com.example.aicoach.dto;

import lombok.Data;
import lombok.Getter;
import lombok.Setter;

import java.util.List;

/**
 * 用于接收客户端确认的学习大纲的数据传输对象 (DTO)。
 * 这个结构与 Python AI 服务生成的 `StudyOutlineResponse` 相对应。
 */
@Data
public class OutlineConfirmationRequest {
    private String title;
    private String overview;
    private List<StudyChapterDto> chapters;
}
