<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="layout">
    <header class="header">
      <RouterLink to="/" class="brand">AI Learning Coach</RouterLink>
      <nav class="nav">
        <RouterLink to="/outline">学习大纲</RouterLink>
        <RouterLink to="/knowledge">知识库</RouterLink>
        <RouterLink to="/chat">RAG 问答</RouterLink>
        <RouterLink to="/plan">每日计划</RouterLink>
      </nav>
    </header>
    <main class="main">
      <RouterView />
    </main>
    <footer class="footer">
      开发模式默认通过 Vite 代理访问 Java :8080 与 AI :8000
    </footer>
  </div>
</template>
