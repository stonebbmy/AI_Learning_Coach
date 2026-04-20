
package com.example.aicoach.controller;

import com.example.aicoach.dto.ChatRequest;
import com.example.aicoach.service.ChatService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
@Tag(name = "4. Chat", description = "与AI学习助理进行问答")
public class ChatController {

    private final ChatService chatService;

    @PostMapping(produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "流式问答接口", 
               description = "将问答请求转发到 Python 的 RAG 服务，并以 SSE (Server-Sent Events) 形式流式返回答案。体现了 WebClient 的使用。")
    public Flux<String> chat(@RequestBody ChatRequest request) {
        return chatService.streamChat(request);
    }
    
    // 可以在这里再增加一个接口，用于在客户端接收完流式响应后，将完整的对话内容一次性发回保存
    // @PostMapping("/histo   ry")
    // public ResponseEntity<Void> saveHistory(@RequestBody ChatHistoryRequest request) {
    //     chatService.saveChatHistory(request.getSessionId(), request.getQuestion(), request.getAnswer());
    //     return ResponseEntity.ok().build();
    // }
}
