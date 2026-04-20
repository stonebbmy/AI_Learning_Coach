
package com.example.aicoach.service;

import com.example.aicoach.dto.ChatRequest;
import com.example.aicoach.entity.ChatHistory;
import com.example.aicoach.repository.ChatHistoryRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
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

    public ChatService(WebClient.Builder webClientBuilder, 
                       @Value("${ai-service.url}") String aiServiceUrl,
                       ChatHistoryRepository chatHistoryRepository) {
        this.webClient = webClientBuilder.baseUrl(aiServiceUrl).build();
        this.chatHistoryRepository = chatHistoryRepository;
    }

    /**
     * 调用 Python 服务的 /chat 接口，并以流式（SSE）方式返回响应。
     * @param request 包含问题和会话ID的请求
     * @return 一个包含字符串块的 Flux 流
     */
    public Flux<String> streamChat(ChatRequest request) {
        log.error("=== start: 2026-04-19-001 ===");
        log.info("开始流式调用AI聊天服务，问题: '{}'", request.getQuestion());
        ObjectMapper mapper = new ObjectMapper();
        String json = null;
        try {
            json = mapper.writeValueAsString(request);
        } catch (JsonProcessingException e) {
            throw new RuntimeException(e);
        }
        System.out.println("=== Sending JSON to AI: " + json);
        log.info("Sending JSON: {}", json);
        return webClient.post()
                .uri("/chat")
                .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .doFirst(() -> {
                    // 流被订阅时执行
                    log.error("=== start: 2026-04-19-001 ===");
                    log.info("开始调用AI服务: {}", request.getQuestion());
                })
                .doOnError(error -> log.error("调用AI聊天服务时发生错误", error))
                .doOnComplete(() -> log.info("AI聊天服务流式响应完成。"));
    }
    
    /**
     * 保存一次完整的问答历史记录。
     * 注意：在流式场景下，需要由客户端在接收完所有数据后，再发起一次请求来保存完整记录。
     * @param sessionId 会话ID
     * @param question 用户的问题
     * @param answer AI的完整回答
     */
    @Transactional
    public void saveChatHistory(String sessionId, String question, String answer) {
        try {
            ChatHistory history = new ChatHistory();
            history.setSessionId(sessionId);
            history.setQuestion(question);
            history.setAnswer(answer);
            history.setTimestamp(LocalDateTime.now());
            chatHistoryRepository.save(history);
            log.info("会话 '{}' 的聊天记录已保存。", sessionId);
        } catch (Exception e) {
            log.error("保存聊天记录失败", e);
        }
    }
}
