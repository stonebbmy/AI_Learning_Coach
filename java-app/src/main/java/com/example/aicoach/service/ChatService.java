
package com.example.aicoach.service;

import com.example.aicoach.dto.ChatRequest;
import com.example.aicoach.entity.ChatHistory;
import com.example.aicoach.repository.ChatHistoryRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;

@Service
@Slf4j
public class ChatService {

    private final WebClient webClient;
    private final ChatHistoryRepository chatHistoryRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ChatService(WebClient.Builder webClientBuilder,
                       @Value("${ai-service.url}") String aiServiceUrl,
                       ChatHistoryRepository chatHistoryRepository) {
        this.webClient = webClientBuilder.baseUrl(aiServiceUrl).build();
        this.chatHistoryRepository = chatHistoryRepository;
    }

    /**
     * 调用 Python 服务的 /chat 接口，以流式（SSE）方式返回响应。
     * ChatRequest 中若携带 plan_context，Python 侧将注入 system message。
     */
    public Flux<String> streamChat(ChatRequest request) {
        log.info("开始流式调用 AI 聊天服务，session={} question='{}'",
                request.getSessionId(), request.getQuestion());
        try {
            log.debug("Sending to Python: {}", objectMapper.writeValueAsString(request));
        } catch (JsonProcessingException ignored) {}

        return webClient.post()
                .uri("/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .doOnError(error -> log.error("调用 AI 聊天服务时发生错误", error))
                .doOnComplete(() -> log.info("AI 聊天服务流式响应完成，session={}", request.getSessionId()));
    }

    /**
     * 异步保存完整的问答历史记录到 PostgreSQL。
     * 在流式结束后由控制层调用，不阻塞响应链路。
     */
    @Async
    @Transactional
    public void saveChatHistory(String sessionId, String question, String answer, String userId) {
        try {
            ChatHistory history = new ChatHistory();
            history.setSessionId(sessionId);
            history.setQuestion(question);
            history.setAnswer(answer);
            history.setUserId(userId);
            history.setTimestamp(LocalDateTime.now());
            chatHistoryRepository.save(history);
            log.info("会话 '{}' 用户 '{}' 的聊天记录已保存。", sessionId, userId);
        } catch (Exception e) {
            log.error("保存聊天记录失败", e);
        }
    }
}
