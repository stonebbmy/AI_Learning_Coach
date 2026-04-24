
package com.example.aicoach.filter;

/**
 * 线程级用户上下文持有者。
 * Filter 从请求头 X-User-Id 提取用户 ID 并存入 ThreadLocal，
 * 同一请求链路内的任意组件均可无参读取。
 */
public final class UserContextHolder {

    private static final ThreadLocal<String> USER_ID = new ThreadLocal<>();

    private UserContextHolder() {}

    public static void set(String userId) {
        USER_ID.set(userId);
    }

    public static String get() {
        String id = USER_ID.get();
        return (id != null && !id.isBlank()) ? id : "anonymous";
    }

    public static void clear() {
        USER_ID.remove();
    }
}
