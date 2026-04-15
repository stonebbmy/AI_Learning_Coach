
package com.example.aicoach.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.util.List;

@Entity
@Getter
@Setter
@Table(name = "study_chapters")
public class StudyChapter {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String chapterTitle;

    @Column(columnDefinition = "TEXT")
    private String description;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "chapter_key_points", joinColumns = @JoinColumn(name = "chapter_id"))
    @Column(name = "key_point", columnDefinition = "TEXT")
    private List<String> keyPoints;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "study_outline_id")
    @JsonIgnore // 避免序列化时产生循环引用
    private StudyOutline studyOutline;
}
