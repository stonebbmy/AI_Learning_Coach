package com.example.aicoach.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

/**
 * 无当日计划且未提供生成条件（如空 goal、不应调 AI）时，映射为 404。
 */
@ResponseStatus(HttpStatus.NOT_FOUND)
public class NoTodayPlanException extends RuntimeException {
    public NoTodayPlanException(String message) {
        super(message);
    }
}
