
package com.example.aicoach.feign;

import com.example.aicoach.dto.ChatAgentResponse;
import com.example.aicoach.dto.ChatRequest;
import com.example.aicoach.dto.DailyPlanRequest;
import com.example.aicoach.dto.DailyPlanResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

/**
 * OpenFeign 客户端，用于声明式地调用 Python AI 服务。
 * `name` 属性用于 Resilience4j 熔断器配置的匹配。
 * `url` 从 application.yml 文件中读取 `ai-service.url` 属性。
 */
@FeignClient(name = "ai-service", url = "${ai-service.url}")
public interface AiServiceClient {

    /**
     * 调用 Python 服务的 /plan/daily 接口来生成每日计划。
     * @param request 包含今日目标的请求体
     * @return 从 Python 服务返回的每日计划
     */
    @PostMapping("/plan/daily")
    DailyPlanResponse getDailyPlan(@RequestBody DailyPlanRequest request);

    /**
     * 非流式工具调用 Agent（与 WebClient 转发的 SSE /chat 互补）。
     */
    @PostMapping("/chat/agent")
    ChatAgentResponse chatAgent(@RequestBody ChatRequest request);

    // 注意：/chat 接口因为是流式响应(SSE)，不适合使用标准 OpenFeign 客户端。
    // 我们将在 Service 层使用 WebClient 来处理流式调用。
}
