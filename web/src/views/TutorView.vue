<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { userStore } from '../lib/userStore'
import { streamTutorChat, updateTutorContext } from '../lib/api'

// ── 会话状态 ──────────────────────────────────────────────────────────────────
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  intent?: string
  actions?: string[]
  isStreaming?: boolean
}

const messages = ref<ChatMessage[]>([])
const input = ref('')
const isLoading = ref(false)
const abortController = ref<AbortController | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

// 当前检测到的意图
const currentIntent = ref('')
const intentLabels: Record<string, string> = {
  ONBOARD: '🚀 新建计划',
  PLAN: '📅 制定计划',
  LEARN: '📖 知识学习',
  REVIEW: '🔄 间隔复习',
  PROGRESS: '📊 进度更新',
  QUIZ: '📝 测验模式',
  EXPLORE: '🌐 探索发现',
}

// ── 用户上下文 ────────────────────────────────────────────────────────────────
const sessionId = computed(() => `tutor_${userStore.state.userId}`)

// ── 快捷指令 ──────────────────────────────────────────────────────────────────
const quickCommands = [
  { label: '今天学什么？', icon: '📅' },
  { label: '考考我吧', icon: '📝' },
  { label: '帮我复习上次的内容', icon: '🔄' },
  { label: '查看我的学习进度', icon: '📊' },
  { label: '我刚完成了今天的任务', icon: '✅' },
]

// ── 发送消息 ──────────────────────────────────────────────────────────────────
async function sendMessage(text?: string) {
  const question = (text ?? input.value).trim()
  if (!question || isLoading.value) return

  input.value = ''
  isLoading.value = true
  currentIntent.value = ''

  messages.value.push({ role: 'user', content: question })

  // 占位助手消息（流式填充）
  const assistantMsg: ChatMessage = {
    role: 'assistant',
    content: '',
    isStreaming: true,
  }
  messages.value.push(assistantMsg)
  await scrollToBottom()

  abortController.value = new AbortController()

  try {
    await streamTutorChat(
      question,
      sessionId.value,
      {
        onIntent(intent) {
          currentIntent.value = intent
          assistantMsg.intent = intent
        },
        onActions(actions) {
          assistantMsg.actions = actions
        },
        onChunk(text) {
          assistantMsg.content += text
          scrollToBottom()
        },
        onEnd() {
          assistantMsg.isStreaming = false
        },
        onError(msg) {
          assistantMsg.content = assistantMsg.content || `⚠️ ${msg}`
          assistantMsg.isStreaming = false
        },
      },
      abortController.value.signal,
    )
  } catch (err: unknown) {
    if (err instanceof Error && err.name !== 'AbortError') {
      assistantMsg.content = assistantMsg.content || '⚠️ 连接失败，请检查服务是否正常运行。'
    }
    assistantMsg.isStreaming = false
  } finally {
    isLoading.value = false
    currentIntent.value = ''
    abortController.value = null
    await scrollToBottom()
  }
}

function abortStream() {
  abortController.value?.abort()
  isLoading.value = false
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

// ── 欢迎消息 ──────────────────────────────────────────────────────────────────
onMounted(() => {
  messages.value.push({
    role: 'assistant',
    content:
      `👋 你好！我是你的 **AI 学习私教**。\n\n` +
      `我可以帮你：\n` +
      `- 📅 制定个性化学习计划\n` +
      `- 📖 解答知识性问题\n` +
      `- 📝 出题检验理解\n` +
      `- 🔄 安排间隔复习\n` +
      `- 📊 追踪学习进度\n\n` +
      `直接用自然语言和我对话，或使用下方快捷指令开始！`,
  })

  // 同步当前用户上下文到 Python Redis
  syncContextOnMount()
})

async function syncContextOnMount() {
  try {
    await updateTutorContext({
      currentOutlineId: userStore.state.currentOutlineId,
      currentPlanId: userStore.state.currentPlanId,
    })
  } catch {
    // 静默失败，不影响使用
  }
}

// ── Markdown 简单渲染 ─────────────────────────────────────────────────────────
function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
    .replace(/#{1,3}\s(.+)/g, '<b>$1</b>')
}
</script>

<template>
  <div class="tutor-layout">
    <!-- ── 上下文状态栏 ─────────────────────────────────────────────────────── -->
    <div class="context-bar">
      <div class="context-item">
        <span class="context-label">用户</span>
        <span class="context-value">{{ userStore.state.userId.slice(0, 12) }}...</span>
      </div>
      <div class="context-item" v-if="userStore.state.currentOutlineId">
        <span class="context-label">📚 大纲</span>
        <span class="context-value">#{{ userStore.state.currentOutlineId }}</span>
      </div>
      <div class="context-item" v-if="userStore.state.currentPlanId">
        <span class="context-label">📅 计划</span>
        <span class="context-value">#{{ userStore.state.currentPlanId }}</span>
      </div>
      <div class="context-item" v-if="currentIntent">
        <span class="intent-badge">{{ intentLabels[currentIntent] || currentIntent }}</span>
      </div>
      <div class="context-tip" v-if="!userStore.state.currentOutlineId">
        💡 前往<router-link to="/outline">大纲页</router-link>创建学习计划，私教将获得更多上下文
      </div>
    </div>

    <!-- ── 消息区域 ────────────────────────────────────────────────────────── -->
    <div class="messages-container" ref="scrollContainer">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message-row"
        :class="msg.role"
      >
        <div class="avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="bubble-wrapper">
          <!-- 动作徽章 -->
          <div class="action-badges" v-if="msg.actions && msg.actions.length">
            <span v-for="action in msg.actions" :key="action" class="action-badge">
              {{ action }}
            </span>
          </div>
          <!-- 消息正文 -->
          <div class="bubble" :class="{ streaming: msg.isStreaming }">
            <span v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)" />
            <span v-else>{{ msg.content }}</span>
            <span v-if="msg.isStreaming" class="cursor-blink">▋</span>
          </div>
        </div>
      </div>

      <!-- 加载动画 -->
      <div v-if="isLoading && !messages[messages.length - 1]?.isStreaming" class="loading-row">
        <div class="avatar">🤖</div>
        <div class="loading-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <!-- ── 快捷指令区 ──────────────────────────────────────────────────────── -->
    <div class="quick-commands" v-if="messages.length <= 1">
      <button
        v-for="cmd in quickCommands"
        :key="cmd.label"
        class="quick-btn"
        @click="sendMessage(cmd.label)"
      >
        {{ cmd.icon }} {{ cmd.label }}
      </button>
    </div>

    <!-- ── 输入区 ─────────────────────────────────────────────────────────── -->
    <div class="input-area">
      <textarea
        ref="inputEl"
        v-model="input"
        class="input-box"
        placeholder="和你的 AI 私教说点什么..."
        rows="2"
        :disabled="isLoading"
        @keydown="handleKeydown"
      />
      <div class="input-actions">
        <button
          v-if="isLoading"
          class="btn btn-stop"
          @click="abortStream"
        >
          ⏹ 停止
        </button>
        <button
          v-else
          class="btn btn-send"
          :disabled="!input.trim()"
          @click="sendMessage()"
        >
          发送 ↗
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tutor-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  max-width: 900px;
  margin: 0 auto;
  gap: 0;
}

/* ── 上下文状态栏 ─────────────────────────────────────────────────────────── */
.context-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #f0f7ff;
  border: 1px solid #d0e8ff;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  flex-wrap: wrap;
}

.context-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.context-label {
  color: #666;
}

.context-value {
  font-weight: 500;
  color: #333;
  font-family: monospace;
}

.intent-badge {
  background: #e8f4fd;
  color: #1a6fcc;
  border: 1px solid #bee3ff;
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.context-tip {
  color: #888;
  font-size: 12px;
  margin-left: auto;
}

.context-tip a {
  color: #1a6fcc;
  text-decoration: none;
}

/* ── 消息区域 ────────────────────────────────────────────────────────────── */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  font-size: 24px;
  flex-shrink: 0;
  margin-top: 4px;
}

.bubble-wrapper {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-row.user .bubble-wrapper {
  align-items: flex-end;
}

.action-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.action-badge {
  background: #f0f0f0;
  color: #555;
  border-radius: 10px;
  padding: 2px 8px;
  font-size: 11px;
}

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.65;
  word-break: break-word;
  background: #fff;
  border: 1px solid #e8e8e8;
  color: #222;
  font-size: 14px;
  white-space: pre-wrap;
}

.message-row.user .bubble {
  background: #1a6fcc;
  color: #fff;
  border-color: #1a6fcc;
}

.bubble.streaming {
  border-color: #90caf9;
  background: #fafeff;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #1a6fcc;
}

@keyframes blink {
  50% { opacity: 0; }
}

.loading-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.loading-dots {
  display: flex;
  gap: 6px;
  padding: 12px 16px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: #1a6fcc;
  border-radius: 50%;
  animation: dot-bounce 1.2s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-6px); opacity: 1; }
}

/* ── 快捷指令 ────────────────────────────────────────────────────────────── */
.quick-commands {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 0;
}

.quick-btn {
  background: #fff;
  border: 1px solid #d0e8ff;
  color: #1a6fcc;
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.quick-btn:hover {
  background: #e8f4ff;
  border-color: #90caf9;
}

/* ── 输入区 ──────────────────────────────────────────────────────────────── */
.input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding-top: 12px;
  border-top: 1px solid #e8e8e8;
}

.input-box {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  font-size: 14px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.15s;
  background: #fff;
}

.input-box:focus {
  outline: none;
  border-color: #1a6fcc;
}

.input-box:disabled {
  background: #f8f8f8;
}

.input-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.btn {
  padding: 10px 18px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-send {
  background: #1a6fcc;
  color: #fff;
}

.btn-send:hover:not(:disabled) {
  background: #1558a8;
}

.btn-send:disabled {
  background: #b0c8e8;
  cursor: not-allowed;
}

.btn-stop {
  background: #ff4d4f;
  color: #fff;
}

.btn-stop:hover {
  background: #cc3d3f;
}
</style>
