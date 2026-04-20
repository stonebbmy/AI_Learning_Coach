<script setup lang="ts">
import { ref } from 'vue'
import { chatAgent, visionProbe, type ChatAgentResponse } from '@/lib/api'

const question = ref('现在几点？并帮我在笔记里搜一下 LangChain 相关内容。')
const sessionId = ref('agent-' + Math.random().toString(36).slice(2, 10))
const loading = ref(false)
const error = ref('')
const result = ref<ChatAgentResponse | null>(null)

const visionUrl = ref('https://modelcontextprotocol.io/favicon.ico')
const visionQ = ref('这张图片里有什么？')
const visionLoading = ref(false)
const visionOut = ref<string>('')

async function onRunAgent() {
  error.value = ''
  result.value = null
  loading.value = true
  try {
    result.value = await chatAgent(question.value.trim(), sessionId.value.trim() || 'default_session')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function onVisionProbe() {
  visionOut.value = ''
  visionLoading.value = true
  try {
    const data = await visionProbe(visionUrl.value.trim(), visionQ.value.trim())
    visionOut.value = JSON.stringify(data, null, 2)
  } catch (e) {
    visionOut.value = e instanceof Error ? e.message : String(e)
  } finally {
    visionLoading.value = false
  }
}
</script>

<template>
  <div>
    <h1>工具 Agent（ReAct）</h1>
    <p class="lead">
      经 Java <code>POST /api/chat/agent</code> 调用 Python
      <code>langgraph.prebuilt.create_react_agent</code>，可调用时间与笔记检索工具。
    </p>

    <div class="card">
      <label>会话 ID</label>
      <input v-model="sessionId" type="text" />

      <label style="margin-top: 0.75rem">输入</label>
      <textarea v-model="question" rows="4" />

      <div style="margin-top: 1rem">
        <button type="button" :disabled="loading || !question.trim()" @click="onRunAgent">
          {{ loading ? '执行中…' : '运行 Agent' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="result" class="card">
      <h2>回答</h2>
      <div class="stream-out">{{ result.answer || '（空）' }}</div>
      <p v-if="result.request_id || result.requestId" class="meta">
        request_id:
        {{ result.request_id ?? result.requestId }}
      </p>
    </div>

    <div class="card">
      <h2>多模态（占位）</h2>
      <p class="lead" style="font-size: 0.9rem">
        直连 Python <code>/api/chat/vision-probe</code>；未开启多模态时预期返回 503，用于验证代理与错误处理。
      </p>
      <label>图片 URL</label>
      <input v-model="visionUrl" type="text" />
      <label style="margin-top: 0.75rem">问题</label>
      <input v-model="visionQ" type="text" />
      <div style="margin-top: 0.75rem">
        <button type="button" class="secondary" :disabled="visionLoading" @click="onVisionProbe">
          {{ visionLoading ? '请求中…' : '探测接口' }}
        </button>
      </div>
      <pre v-if="visionOut" class="vision-pre">{{ visionOut }}</pre>
    </div>
  </div>
</template>

<style scoped>
.meta {
  margin-top: 0.75rem;
  font-size: 0.8rem;
  color: var(--muted, #8b9cb3);
}
.vision-pre {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg, #0f1419);
  border: 1px solid var(--border, #2d3a4d);
  border-radius: 6px;
  font-size: 0.8rem;
  overflow: auto;
  max-height: 200px;
}
</style>
