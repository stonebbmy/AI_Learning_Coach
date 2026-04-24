
package com.example.aicoach.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

@Entity
@Getter
@Setter
@Table(name = "tasks")
public class Task {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private int taskId;

    @Column(columnDefinition = "TEXT")
    private String description;

    private String estimatedTime;

    /** 任务状态：待开始 / 进行中 / 已完成 */
    private String status;

    /** 任务完成时间，状态变更为"已完成"时自动写入 */
    private LocalDateTime completedAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "daily_plan_id")
    @JsonIgnore
    private DailyPlan dailyPlan;
}
