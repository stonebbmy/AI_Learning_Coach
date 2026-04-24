<script setup lang="ts">
import { ref } from 'vue'
import { streamChat } from '@/lib/api'
import { userStore } from '@/lib/userStore'

interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

const question = ref('请根据我的笔记总结：RAG 检索流程是怎样的？')
const sessionId = ref('web-' + Math.random().toString(36).slice(2, 10))
/** 已完成的多轮对话，会作为 messages 传给后端（与 Redis 短期记忆二选一/互补） */
const transcript = ref<ChatTurn[]>([])
const answer = ref('')
const loading = ref(false)
const error = ref('')
let abort: AbortController | null = null

async function onSend() {
  const q = question.value.trim()
  if (!q) return
  error.value = ''
  answer.value = ''
  loading.value = true
  abort = new AbortController()
  try {
    const history =
      transcript.value.length > 0
        ? transcript.value.map((m) => ({ role: m.role, content: m.content }))
        : undefined
    await streamChat(
      q,
      sessionId.value.trim() || 'default_session',
      (chunk) => {
        answer.value += chunk
      },
      abort.signal,
      history,
      userStore.state.currentPlanId,
    )
    transcript.value = [...transcript.value, { role: 'user', content: q }, { role: 'assistant', content: answer.value }]
    question.value = ''
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

function clearSession() {
  transcript.value = []
  answer.value = ''
  error.value = ''
  sessionId.value = 'web-' + Math.random().toString(36).slice(2, 10)
}
</script>

<template>
  <div>
    <h1>RAG 问答</h1>
    <p class="lead">
      经 Java <code>POST /api/chat</code> 转发 Python SSE；支持多轮（messages + sessionId）。
      <span v-if="userStore.state.currentPlanId" style="color: var(--muted); font-size: 0.9rem">
        · 已关联今日计划 #{{ userStore.state.currentPlanId }}，AI 将结合计划上下文回答
      </span>
    </p>

    <div class="card">
      <label>会话 ID</label>
      <input v-model="sessionId" type="text" />

      <div v-if="transcript.length" class="transcript">
        <div
          v-for="(m, i) in transcript"
          :key="i"
          class="msg"
          :class="m.role === 'user' ? 'msg-user' : 'msg-assistant'"
        >
          <span class="msg-role">{{ m.role === 'user' ? '你' : '助手' }}</span>
          <div class="msg-body">{{ m.content }}</div>
        </div>
      </div>

      <label style="margin-top: 0.75rem">新问题</label>
      <textarea v-model="question" rows="4" placeholder="输入问题后发送…" />

      <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap">
        <button type="button" :disabled="loading || !question.trim()" @click="onSend">
          {{ loading ? '生成中…' : '发送' }}
        </button>
        <button type="button" class="secondary" :disabled="!loading" @click="onStop">停止</button>
        <button type="button" class="secondary" :disabled="loading" @click="clearSession">清空会话</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="loading || answer" class="card">
      <h2>当前回答</h2>
      <div class="stream-out">{{ answer || '（等待首字…）' }}</div>
    </div>
  </div>
</template>

<style scoped>
.transcript {
  margin-top: 0.75rem;
  max-height: 280px;
  overflow-y: auto;
  padding: 0.5rem;
  background: var(--bg, #0f1419);
  border-radius: 6px;
  border: 1px solid var(--border, #2d3a4d);
}
.msg {
  margin-bottom: 0.65rem;
}
.msg:last-child {
  margin-bottom: 0;
}
.msg-role {
  font-size: 0.75rem;
  color: var(--muted, #8b9cb3);
  display: block;
  margin-bottom: 0.2rem;
}
.msg-user .msg-body {
  border-left: 3px solid var(--accent, #3b82f6);
  padding-left: 0.5rem;
}
.msg-assistant .msg-body {
  border-left: 3px solid #64748b;
  padding-left: 0.5rem;
}
.msg-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.92rem;
}
</style>
