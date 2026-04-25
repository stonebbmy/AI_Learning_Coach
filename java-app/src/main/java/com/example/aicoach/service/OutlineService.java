package com.example.aicoach.service;

import com.example.aicoach.entity.StudyOutline;
import com.example.aicoach.repository.DailyPlanRepository;
import com.example.aicoach.repository.StudyOutlineRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
@RequiredArgsConstructor
public class OutlineService {

    private final StudyOutlineRepository studyOutlineRepository;
    private final DailyPlanRepository dailyPlanRepository;

    @Transactional
    public void deleteOutlineForUser(Long outlineId, String userId) {
        StudyOutline outline = studyOutlineRepository.findById(outlineId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "大纲不存在"));
        if (outline.getUserId() == null || !outline.getUserId().equals(userId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "无权删除该大纲");
        }
        dailyPlanRepository.clearSourceOutlineIdByOutlineId(outlineId);
        studyOutlineRepository.delete(outline);
    }
}
