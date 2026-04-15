
package com.example.aicoach.config;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;

import java.time.Duration;

/**
 * Spring Cache with Redis 的全局配置。
 */
@Configuration
@EnableCaching // 开启Spring的缓存功能
public class CacheConfig {

    /**
     * 定义默认的 Redis 缓存行为。
     * @return RedisCacheConfiguration
     */
    @Bean
    public RedisCacheConfiguration cacheConfiguration() {
        return RedisCacheConfiguration.defaultCacheConfig()
                // 设置缓存的默认过期时间为24小时，符合“当日计划”的缓存需求
                .entryTtl(Duration.ofHours(24))
                // 禁止缓存 null 值，防止缓存穿透问题
                .disableCachingNullValues()
                // 设置值的序列化器为 JSON 格式，提高可读性
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()));
    }
}
