
package com.example.aicoach;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * AI Learning Coach - Java Application Entry Point
 */
@SpringBootApplication
@EnableFeignClients // 启用 OpenFeign 声明式客户端功能
// @EnableCaching is already on CacheConfig, so it's not strictly needed here.
public class AiCoachApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiCoachApplication.class, args);
    }

}
