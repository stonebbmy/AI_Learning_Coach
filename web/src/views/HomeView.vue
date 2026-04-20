<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div>
    <h1>AI Learning Coach</h1>
    <p class="lead">
      Java 业务层（8080）+ Python AI 层（8000）：大纲生成、知识库上传、RAG 流式问答、每日学习计划。
    </p>
    <div class="card">
      <h2>功能入口</h2>
      <ul>
        <li><RouterLink to="/outline">学习大纲</RouterLink>：调用 AI 生成结构化大纲，并可确认保存到数据库。</li>
        <li><RouterLink to="/knowledge">知识库</RouterLink>：上传 Markdown 笔记写入向量库。</li>
        <li><RouterLink to="/chat">RAG 问答</RouterLink>：基于笔记上下文的流式对话（经 Java 转发 SSE），支持多轮 transcript。</li>
        <li><RouterLink to="/agent">工具 Agent</RouterLink>：ReAct 工具调用（时间、笔记检索），非流式 JSON。</li>
        <li><RouterLink to="/plan">每日计划</RouterLink>：按今日目标获取学习计划（缓存 + 数据库 + LangGraph）。</li>
      </ul>
    </div>
    <p class="lead" style="font-size: 0.85rem">
      本地开发请先启动 <code>docker compose up -d</code>，再在本目录执行 <code>npm install</code> 与
      <code>npm run dev</code>。
    </p>
  </div>
</template>
