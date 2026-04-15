
package com.example.aicoach.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@Setter
@Table(name = "study_outlines")
public class StudyOutline {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String title;

    @Column(columnDefinition = "TEXT")
    private String overview;

    @OneToMany(mappedBy = "studyOutline", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    private List<StudyChapter> chapters = new ArrayList<>();

    public void setChapters(List<StudyChapter> chapters) {
        this.chapters = chapters;
        for (StudyChapter chapter : chapters) {
            chapter.setStudyOutline(this);
        }
    }
}
