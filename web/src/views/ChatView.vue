<script setup lang="ts">
import { ref } from 'vue'
import { streamChat } from '@/lib/api'

const question = ref('请根据我的笔记总结：RAG 检索流程是怎样的？')
const sessionId = ref('web-' + Math.random().toString(36).slice(2, 10))
const answer = ref('')
const loading = ref(false)
const error = ref('')
let abort: AbortController | null = null

async function onSend() {
  error.value = ''
  answer.value = ''
  loading.value = true
  abort = new AbortController()
  try {
    await streamChat(
      question.value.trim(),
      sessionId.value.trim() || 'default_session',
      (chunk) => {
        answer.value += chunk
      },
      abort.signal
    )
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
    abort = null
  }
}

function onStop() {
  abort?.abort()
}
</script>

<template>
  <div>
    <h1>RAG 问答</h1>
    <p class="lead">经 Java <code>POST /api/chat</code> 转发 Python SSE 流式输出。</p>

    <div class="card">
      <label>会话 ID</label>
      <input v-model="sessionId" type="text" />

      <label style="margin-top: 0.75rem">问题</label>
      <textarea v-model="question" rows="4" />

      <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap">
        <button type="button" :disabled="loading || !question.trim()" @click="onSend">
          {{ loading ? '生成中…' : '发送' }}
        </button>
        <button type="button" class="secondary" :disabled="!loading" @click="onStop">停止</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div class="card">
      <h2>回答</h2>
      <div class="stream-out">{{ answer || '（等待输出）' }}</div>
    </div>
  </div>
</template>
