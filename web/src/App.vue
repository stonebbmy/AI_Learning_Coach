<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const isLearningModule = computed(() =>
  ['outline', 'plan', 'progress', 'tutor-guide', 'knowledge'].includes(String(route.name)),
)

const isEmbedRoute = computed(() =>
  ['prometheus', 'grafana'].includes(String(route.name)),
)

const isDashboardWide = computed(() =>
  ['metrics', 'eval'].includes(String(route.name)),
)

/** 普通页 main 整列滚动，私教/学习模块由内部分区滚动，嵌入页由 iframe 内滚动 */
const mainScrollY = computed(
  () => route.name !== 'tutor' && !isLearningModule.value && !isEmbedRoute.value,
)
</script>

<template>
  <div
    class="layout"
    :class="{ 'layout--tutor': route.name === 'tutor' || isLearningModule }"
  >
    <header class="header">
      <RouterLink to="/" class="brand">AI Learning Coach</RouterLink>
      <nav class="nav">
        <RouterLink to="/" class="nav-primary">🤖 AI 私教</RouterLink>
        <span class="nav-sep">|</span>
        <RouterLink to="/tutor-guide" class="nav-flow">📖 功能简介</RouterLink>
        <RouterLink to="/outline" class="nav-flow">📋 大纲</RouterLink>
        <RouterLink to="/plan" class="nav-flow">📅 计划</RouterLink>
        <RouterLink to="/progress" class="nav-flow">📊 进度</RouterLink>
        <RouterLink to="/knowledge" class="nav-flow">📁 知识库</RouterLink>
        <span class="nav-sep">|</span>
        <RouterLink to="/chat" class="nav-tool">RAG问答</RouterLink>
        <RouterLink to="/agent" class="nav-tool">Agent</RouterLink>
        <RouterLink to="/metrics" class="nav-tool">监控</RouterLink>
        <RouterLink to="/eval" class="nav-tool">评估</RouterLink>
        <RouterLink to="/prometheus" class="nav-tool">📈 Prometheus</RouterLink>
        <RouterLink to="/grafana" class="nav-tool">📉 Grafana</RouterLink>
      </nav>
    </header>
    <main
      class="main"
      :class="{
        'main--tutor': route.name === 'tutor',
        'main--learning': isLearningModule,
        'main--embed': isEmbedRoute,
        'main--dashboard': isDashboardWide,
        'scroll-y': mainScrollY,
      }"
    >
      <RouterView />
    </main>
    <footer class="footer">
      开发模式 · Vite Proxy → Java :8080 / AI :8000 &nbsp;|&nbsp;
      AI 私教已接入三层记忆（滚动摘要 + 长期语义 + 近期窗口）
    </footer>
  </div>
</template>

<style scoped>
.nav-primary {
  font-weight: 700;
  color: #fff !important;
  background: #3b4db8;
  border-radius: 6px;
  padding: 3px 10px;
}
.nav-sep {
  color: var(--border, #2e3450);
  user-select: none;
  margin: 0 2px;
}
.nav-flow {
  color: var(--text, #c0ccee) !important;
  font-size: 0.88rem;
}
.nav-flow.router-link-active {
  color: #8ab4f8 !important;
  font-weight: 600;
}
.nav-tool {
  font-size: 0.8rem;
  color: var(--muted, #8899cc) !important;
  opacity: 0.8;
}
.nav-tool.router-link-active {
  opacity: 1;
  color: #8ab4f8 !important;
}
</style>
