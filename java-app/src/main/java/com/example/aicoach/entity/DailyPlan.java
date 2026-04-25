
package com.example.aicoach.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@Setter
@Table(name = "daily_plans")
public class DailyPlan {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String userId;

    private String planTitle;

    private LocalDate planDate;

    /**
     * 生成该日计划时使用的已确认大纲 ID；无大纲约束生成时为 null。
     */
    @Column(name = "source_outline_id")
    private Long sourceOutlineId;

    /**
     * 生成时使用的学习目标原文，用于与请求对账、历史展示。
     */
    @Column(name = "source_goal", columnDefinition = "TEXT")
    private String sourceGoal;

    @OneToMany(mappedBy = "dailyPlan", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    private List<Task> tasks = new ArrayList<>();

    public void setTasks(List<Task> tasks) {
        this.tasks = tasks;
        for (Task task : tasks) {
            task.setDailyPlan(this);
        }
    }
}
