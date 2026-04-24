
package com.example.aicoach;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * AI Learning Coach - Java Application Entry Point
 */
@SpringBootApplication
@EnableFeignClients
@EnableAsync
public class AiCoachApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiCoachApplication.class, args);
    }

}
