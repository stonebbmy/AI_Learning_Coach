<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { userStore } from '../lib/userStore'
import {
  streamTutorChat,
  updateTutorContext,
  fetchTutorHistory,
  updateTaskStatus,
  confirmOutline,
  toOutlineConfirmBody,
  getTodayPlan,
  type TutorCardPayload,
} from '../lib/api'
import OutlineCard from '../components/OutlineCard.vue'
import QuizCard from '../components/QuizCard.vue'
import PlanCard from '../components/PlanCard.vue'

// ── 消息类型 ──────────────────────────────────────────────────────────────────
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  intent?: string
  actions?: string[]
  card?: TutorCardPayload
  isStreaming?: boolean
}

// ── 会话状态 ──────────────────────────────────────────────────────────────────
const messages = ref<ChatMessage[]>([])
const input = ref('')
const isLoading = ref(false)
const abortController = ref<AbortController | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const currentIntent = ref('')
const sidebarOpen = ref(true)
/** 侧栏中部：仅「今日任务 / 大纲章节」胶囊 Tab 切换 */
const sidebarContentTab = ref<'tasks' | 'chapters'>('tasks')

const intentLabels: Record<string, string> = {
  ONBOARD: '🚀 新建计划',
  PLAN: '📅 制定计划',
  LEARN: '📖 知识学习',
  REVIEW: '🔄 间隔复习',
  PROGRESS: '📊 进度更新',
  QUIZ: '📝 测验模式',
  EXPLORE: '🌐 探索发现',
}

// ── 计算属性 ──────────────────────────────────────────────────────────────────
const sessionId = computed(() => `tutor_${userStore.state.userId}`)

const progressPercent = computed(() => Math.round(userStore.state.progressRate * 100))

const pendingTasks = computed(() =>
  userStore.state.planTasks.filter(
    (t) => !['已完成', 'done', 'DONE', 'completed'].includes(t.status),
  ),
)

const doneTasks = computed(() =>
  userStore.state.planTasks.filter((t) =>
    ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
  ),
)

// ── 快捷指令 ──────────────────────────────────────────────────────────────────
const quickCommands = [
  { label: '我想学习一个新领域', icon: '🚀' },
  { label: '今天学什么？', icon: '📅' },
  { label: '考考我吧', icon: '📝' },
  { label: '帮我复习上次的内容', icon: '🔄' },
  { label: '查看我的学习进度', icon: '📊' },
]

// ── 发送消息 ──────────────────────────────────────────────────────────────────
async function sendMessage(text?: string) {
  const question = (text ?? input.value).trim()
  if (!question || isLoading.value) return

  input.value = ''
  isLoading.value = true
  currentIntent.value = ''

  messages.value.push({ role: 'user', content: question })

  // 通过 reactive 数组索引操作，确保每次 content/isStreaming 变更都经过
  // Vue 的响应式 Proxy，实现打字机效果和流结束后的 Markdown 渲染。
  messages.value.push({ role: 'assistant', content: '', isStreaming: true })
  const msgIdx = messages.value.length - 1
  await scrollToBottom()

  abortController.value = new AbortController()

  try {
    await streamTutorChat(
      question,
      sessionId.value,
      {
        onIntent(intent) {
          currentIntent.value = intent
          messages.value[msgIdx].intent = intent
        },
        onActions(actions) {
          messages.value[msgIdx].actions = actions
        },
        onCard(card) {
          messages.value[msgIdx].card = card
          if (card.type === 'plan') {
            // plan 卡片：同步 store，并异步落库（getTodayPlan 会保存到 DB）
            const tasks = (card.payload as { tasks?: typeof userStore.state.planTasks }).tasks
            if (tasks) {
              userStore.setPlanTasks([...tasks])
              const doneCount = tasks.filter((t) =>
                ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
              ).length
              userStore.setProgressRate(tasks.length > 0 ? doneCount / tasks.length : 0)
              // 异步落库（不阻塞流式显示）
              persistPlanToDb()
            }
          }
          scrollToBottom()
        },
        onChunk(text) {
          messages.value[msgIdx].content = normalizeLineEndings(
            messages.value[msgIdx].content + text,
          )
          scrollToBottom()
        },
        onEnd() {
          messages.value[msgIdx].isStreaming = false
        },
        onError(msg) {
          const m = messages.value[msgIdx]
          m.content = m.content || `⚠️ ${msg}`
          m.isStreaming = false
        },
      },
      abortController.value.signal,
    )
  } catch (err: unknown) {
    if (err instanceof Error && err.name !== 'AbortError') {
      const m = messages.value[msgIdx]
      m.content = m.content || '⚠️ 连接失败，请检查服务是否正常运行。'
    }
    messages.value[msgIdx].isStreaming = false
  } finally {
    // 保底：无论 onEnd 是否触发，都确保 isStreaming 归 false，
    // 使 isLoading=false 引发的重渲染时能正确调用 renderMarkdown。
    if (messages.value[msgIdx]) {
      messages.value[msgIdx].isStreaming = false
    }
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

// ── 任务状态切换（侧边栏点击）───────────────────────────────────────────────
async function toggleTask(taskId: number | undefined, currentStatus: string) {
  if (!taskId) return
  const newStatus = ['已完成', 'done', 'DONE', 'completed'].includes(currentStatus)
    ? '待开始'
    : '已完成'
  try {
    await updateTaskStatus(taskId, newStatus)
    userStore.updateTaskStatus(taskId, newStatus)
    const doneCount = userStore.state.planTasks.filter((t) =>
      ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
    ).length
    userStore.setProgressRate(
      userStore.state.planTasks.length > 0 ? doneCount / userStore.state.planTasks.length : 0,
    )
  } catch {
    /* 静默失败 */
  }
}

// ── 大纲卡片确认：直接调 Java API 保存，然后自动触发制定计划 ────────────────
const savingOutline = ref(false)

async function handleOutlineConfirm(outlinePayload: Record<string, unknown>) {
  if (savingOutline.value) return
  savingOutline.value = true

  // 在消息列表中添加用户确认行为
  messages.value.push({ role: 'user', content: '✅ 确认以上大纲，请帮我制定今日学习计划' })
  await scrollToBottom()

  try {
    // 1. 将 tutor 大纲格式转为 Java API 格式
    const chapters = (outlinePayload.chapters as any[]) ?? []
    const confirmBody = {
      title: String(outlinePayload.title ?? ''),
      overview: String(outlinePayload.goal ?? ''),
      chapters: chapters.map((ch: any) => ({
        chapterTitle: ch.title,
        description: ch.description ?? '',
        keyPoints: ch.key_concepts ?? [],
      })),
    }
    // 2. 调 Java BFF 保存大纲
    const saved = (await confirmOutline(confirmBody)) as { id?: number }
    const outlineId = saved.id ?? null
    const chapterTitles = chapters.map((ch: any) => String(ch.title))

    // 3. 更新本地 store
    userStore.setOutlineId(outlineId)
    userStore.setOutlineChapters(chapterTitles)

    // 4. 同步到 Redis
    await updateTutorContext({
      currentOutlineId: outlineId,
      outlineChapters: chapterTitles,
    }).catch(() => {/* 静默 */})

    // 5. 自动让私教制定今日计划（带大纲ID上下文）
    await sendMessage(`大纲已确认（ID: ${outlineId}），请根据大纲章节帮我制定今日学习计划`)
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: `⚠️ 大纲保存失败：${e instanceof Error ? e.message : String(e)}，请到「大纲」页面手动确认。`,
    })
    await scrollToBottom()
  } finally {
    savingOutline.value = false
  }
}

// ── 将私教生成的计划落库（与「学习」页中计划为同一 BFF，正式改目标/重算以 /plan 为主）─
async function persistPlanToDb() {
  try {
    // 用当前大纲 ID 与从章节名拼的 goal 触发落库（会读已确认大纲章节；非空，不会 404）
    const goal = userStore.state.outlineChapters.slice(0, 2).join('、') || '今日学习'
    const result = await getTodayPlan(goal, userStore.state.currentOutlineId)
    if (result.id) {
      userStore.setPlanId(result.id)
      userStore.setPlanTasks(result.tasks)
      // 同步到私教 Redis 上下文
      await updateTutorContext({
        currentPlanId: result.id,
        planTasks: result.tasks,
        progressRate: 0,
      }).catch(() => {/* 静默 */})
    }
  } catch {
    /* 静默：计划卡片已展示，落库失败不影响对话 */
  }
}

// ── PlanCard 任务切换（点击勾选更新状态 + store）─────────────────────────────
async function handlePlanTaskDone(taskId: number, status: string) {
  try {
    await updateTaskStatus(taskId, status)
    userStore.updateTaskStatus(taskId, status)
    // 重新计算进度
    const doneCount = userStore.state.planTasks.filter((t) =>
      ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
    ).length
    userStore.setProgressRate(
      userStore.state.planTasks.length > 0 ? doneCount / userStore.state.planTasks.length : 0,
    )
  } catch {
    /* 静默失败 */
  }
}

// ── 挂载时恢复历史 + 同步上下文 ──────────────────────────────────────────────
onMounted(async () => {
  // 1. 尝试恢复历史会话
  try {
    const history = await fetchTutorHistory(sessionId.value, 20)
    if (history.messages && history.messages.length > 0) {
      // 将历史记录转为 ChatMessage 格式（过滤掉空内容）
      const restored = history.messages
        .filter((m) => m.content && m.content.trim())
        .map((m) => ({
          role: m.role as 'user' | 'assistant',
          content: normalizeLineEndings(m.content),
        }))
      if (restored.length > 0) {
        messages.value = [
          {
            role: 'assistant',
            content: `📖 已为你恢复最近 ${restored.length} 条对话记录，继续学习吧！`,
          },
          ...restored,
        ]
        await scrollToBottom()
        // 同步上下文
        await syncContextOnMount()
        return
      }
    }
  } catch {
    /* 恢复失败，显示欢迎语 */
  }

  // 2. 无历史记录，显示欢迎消息
  messages.value.push({
    role: 'assistant',
    content:
      `👋 你好！我是你的 **AI 学习私教**。\n\n` +
      `我可以帮你：\n` +
      `- 🚀 生成个性化学习大纲（告诉我你想学什么）\n` +
      `- 📅 制定每日学习计划\n` +
      `- 📖 解答知识性问题（RAG + 知识库）\n` +
      `- 📝 出题检验理解程度\n` +
      `- 🔄 安排间隔复习\n` +
      `- 📊 追踪学习进度\n\n` +
      `直接用自然语言和我对话，或使用下方快捷指令开始！`,
  })

  await syncContextOnMount()
})

async function syncContextOnMount() {
  try {
    await updateTutorContext({
      currentOutlineId: userStore.state.currentOutlineId,
      currentPlanId: userStore.state.currentPlanId,
      outlineChapters: [...userStore.state.outlineChapters],
      planTasks: [...userStore.state.planTasks],
      progressRate: userStore.state.progressRate,
    })
  } catch {
    /* 静默失败 */
  }
}

/** 统一为 \n，避免 \r / \r\n 在流式时显示成「粘成一行」 */
function normalizeLineEndings(text: string): string {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

// ── Markdown 渲染（完整文本时调用，流式期间为纯文本 + pre-wrap）─────────────
function renderMarkdown(text: string): string {
  return (
    normalizeLineEndings(text)
      // 标题
      .replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>')
      .replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>')
      .replace(/^#{1}\s+(.+)$/gm, '<h1>$1</h1>')
      // 加粗 / 斜体
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // 行内代码
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      // 列表行（用 div，避免 <li> 默认圆点且 invalid 嵌在 span 内）
      .replace(/^[-*]\s+(.+)$/gm, '<div class="bubble-md-line">$1</div>')
      // 换行
      .replace(/\n/g, '<br>')
  )
}
</script>

<template>
  <div class="tutor-root">
    <!-- ── 侧边栏 ──────────────────────────────────────────────────────────── -->
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">
        {{ sidebarOpen ? '◀' : '▶' }}
      </button>

      <div v-if="sidebarOpen" class="sidebar-body">
        <div class="sidebar-block sidebar-block--top">
          <div class="progress-ring-wrap">
            <svg class="progress-ring" viewBox="0 0 48 48">
              <circle cx="24" cy="24" r="20" fill="none" stroke="#2e3450" stroke-width="4" />
              <circle
                cx="24" cy="24" r="20" fill="none"
                stroke="#5b72e8" stroke-width="4"
                stroke-dasharray="125.66"
                :stroke-dashoffset="125.66 * (1 - userStore.state.progressRate)"
                stroke-linecap="round"
                transform="rotate(-90 24 24)"
              />
            </svg>
            <span class="progress-pct">{{ progressPercent }}%</span>
          </div>
          <p class="sidebar-label">今日进度</p>
        </div>

        <div class="sidebar-mid">
          <div class="segment" role="tablist" aria-label="任务与章节">
            <button
              type="button"
              role="tab"
              class="segment-btn"
              :class="{ 'is-active': sidebarContentTab === 'tasks' }"
              :aria-selected="sidebarContentTab === 'tasks'"
              @click="sidebarContentTab = 'tasks'"
            >
              今日任务
            </button>
            <button
              type="button"
              role="tab"
              class="segment-btn"
              :class="{ 'is-active': sidebarContentTab === 'chapters' }"
              :aria-selected="sidebarContentTab === 'chapters'"
              @click="sidebarContentTab = 'chapters'"
            >
              大纲章节
            </button>
          </div>

          <div class="sidebar-mid-scroll">
            <div
              v-show="sidebarContentTab === 'tasks'"
              class="sidebar-mid-page"
              role="tabpanel"
            >
              <template v-if="userStore.state.planTasks.length">
                <ul class="task-list">
                  <li
                    v-for="(task, ti) in userStore.state.planTasks"
                    :key="task.task_id"
                    class="task-card"
                    :class="{
                      'is-done': ['已完成', 'done', 'DONE', 'completed'].includes(task.status),
                    }"
                    :title="task.description"
                    @click="toggleTask(task.db_id ?? task.task_id, task.status)"
                  >
                    <div class="task-card__row">
                      <span class="task-card__num" aria-hidden="true">{{ ti + 1 }}</span>
                      <span
                        class="task-card__check"
                        :class="{
                          tick: ['已完成', 'done', 'DONE', 'completed'].includes(task.status),
                        }"
                        aria-hidden="true"
                      >
                        {{ ['已完成', 'done', 'DONE', 'completed'].includes(task.status) ? '✓' : '' }}
                      </span>
                      <div class="task-card__main">
                        <p class="task-card__desc">{{ task.description }}</p>
                        <p v-if="task.estimated_time" class="task-card__meta">
                          预计 {{ task.estimated_time }}
                        </p>
                      </div>
                    </div>
                  </li>
                </ul>
                <div class="task-stat-bar" role="status">
                  {{ doneTasks.length }}/{{ userStore.state.planTasks.length }} 完成
                  <span class="task-stat-dot"></span>
                  {{ pendingTasks.length }} 待做
                </div>
              </template>
              <div v-else class="sidebar-empty sidebar-empty--in-tab">
                <p>还没有今日任务</p>
                <p class="sidebar-empty-hint">在「计划」页生成，或从私教卡片落库</p>
              </div>
            </div>

            <div
              v-show="sidebarContentTab === 'chapters'"
              class="sidebar-mid-page"
              role="tabpanel"
            >
              <template v-if="userStore.state.outlineChapters.length">
                <ul class="chapter-cards">
                  <li
                    v-for="(ch, i) in userStore.state.outlineChapters"
                    :key="i"
                    class="chapter-card"
                    :title="ch"
                  >
                    <span class="chapter-card__num" aria-hidden="true">{{ i + 1 }}</span>
                    <p class="chapter-card__text">{{ ch }}</p>
                  </li>
                </ul>
              </template>
              <div v-else class="sidebar-empty sidebar-empty--in-tab">
                <p>暂无章节</p>
                <p class="sidebar-empty-hint">在「大纲」页生成并「设为当前」后同步</p>
              </div>
            </div>
          </div>
        </div>

        <div class="sidebar-block sidebar-block--nav">
          <router-link to="/tutor-guide" class="shortcut-btn">📖 功能简介</router-link>
          <router-link to="/knowledge" class="shortcut-btn">📁 知识库</router-link>
          <router-link to="/outline" class="shortcut-btn">📋 大纲</router-link>
          <router-link to="/plan" class="shortcut-btn">📅 计划</router-link>
          <router-link to="/progress" class="shortcut-btn">📊 进度</router-link>
        </div>
      </div>
    </aside>

    <!-- ── 主对话区 ──────────────────────────────────────────────────────────── -->
    <div class="chat-pane">
      <!-- 顶部意图状态 -->
      <div class="intent-bar" v-if="currentIntent">
        <span class="intent-badge">{{ intentLabels[currentIntent] || currentIntent }}</span>
        <span class="intent-thinking">思考中...</span>
      </div>

      <!-- 消息列表 -->
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

            <!-- 结构化卡片 -->
            <OutlineCard
              v-if="msg.card && msg.card.type === 'outline'"
              :payload="msg.card.payload as any"
              :saving="savingOutline"
              @confirm="handleOutlineConfirm(msg.card.payload)"
            />
            <PlanCard
              v-else-if="msg.card && msg.card.type === 'plan'"
              :payload="msg.card.payload as any"
              @task-done="handlePlanTaskDone"
            />
            <QuizCard
              v-else-if="msg.card && msg.card.type === 'quiz'"
              :questions="(msg.card.payload as any).questions"
            />

            <!-- 流式：纯文本 + pre-wrap 保留换行；完成：renderMarkdown -->
            <div
              v-if="msg.content"
              class="bubble"
              :class="{
                streaming: msg.isStreaming,
                'stream-plain': msg.role === 'assistant' && msg.isStreaming,
              }"
            >
              <template v-if="msg.role === 'assistant' && msg.isStreaming">
                <span class="stream-text">{{ msg.content }}</span
                ><span class="cursor-blink" aria-hidden="true">▋</span>
              </template>
              <span
                v-else-if="msg.role === 'assistant'"
                v-html="renderMarkdown(msg.content)"
              />
              <span v-else>{{ msg.content }}</span>
            </div>
          </div>
        </div>

        <!-- 加载动画 -->
        <div v-if="isLoading && !messages[messages.length - 1]?.isStreaming" class="loading-row">
          <div class="avatar">🤖</div>
          <div class="loading-dots">
            <span /><span /><span />
          </div>
        </div>
      </div>

      <div class="chat-composer" aria-label="输入与快捷指令">
        <div class="quick-commands" role="toolbar" aria-label="快捷输入">
          <div class="quick-commands-track">
            <button
              v-for="cmd in quickCommands"
              :key="cmd.label"
              type="button"
              class="quick-btn"
              :disabled="isLoading"
              @click="sendMessage(cmd.label)"
            >
              <span class="quick-ico" aria-hidden="true">{{ cmd.icon }}</span> {{ cmd.label }}
            </button>
          </div>
        </div>

        <div class="input-area">
          <div class="input-field-wrap">
            <textarea
              ref="inputEl"
              v-model="input"
              class="input-box"
              placeholder="和你的 AI 私教说点什么... (Enter 发送，Shift+Enter 换行)"
              rows="2"
              :disabled="isLoading"
              @keydown="handleKeydown"
            />
            <button
              v-if="isLoading"
              type="button"
              class="input-embed-btn input-embed-btn--stop"
              aria-label="停止生成"
              @click="abortStream"
            >
              <svg class="input-embed-ico" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" />
              </svg>
            </button>
            <button
              v-else
              type="button"
              class="input-embed-btn input-embed-btn--send"
              :disabled="!input.trim()"
              aria-label="发送"
              @click="sendMessage()"
            >
              <svg class="input-embed-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <polyline
                  points="6 15 12 9 18 15"
                  stroke="currentColor"
                  stroke-width="2.1"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tutor-root {
  display: flex;
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  gap: 0;
  overflow: hidden;
  max-height: 100%;
}

/* ── 侧边栏 ──────────────────────────────────────────────────────────────── */
.sidebar {
  width: 240px;
  min-width: 240px;
  min-height: 0;
  align-self: stretch;
  background: var(--sidebar-bg, #161924);
  border-right: 1px solid var(--border, #2e3450);
  display: flex;
  flex-direction: column;
  padding: 0.75rem 0.6rem 0.5rem;
  gap: 0;
  overflow: hidden;
  transition: width 0.2s, min-width 0.2s;
  position: relative;
}

.sidebar-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-top: 1.35rem;
  overflow: hidden;
}

.sidebar-block--top {
  flex-shrink: 0;
  padding: 0.35rem 0.5rem 0.65rem;
  border-bottom: 1px solid var(--border, #2e3450);
  margin-bottom: 0.25rem;
}

.sidebar-block--nav {
  flex-shrink: 0;
  border-top: 1px solid var(--border, #2e3450);
  margin-top: 0.1rem;
  padding: 0.5rem 0.45rem 0.2rem;
}

.sidebar-mid {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-bottom: 0.35rem;
}

/* 胶囊分段：未选偏灰、选中为亮蓝实底（参考图二） */
.segment {
  display: flex;
  gap: 0.2rem;
  padding: 0.2rem;
  flex-shrink: 0;
  background: rgba(8, 10, 18, 0.65);
  border: 1px solid rgba(46, 52, 80, 0.9);
  border-radius: 999px;
  margin: 0 0 0.45rem;
}
.segment-btn {
  flex: 1;
  border: none;
  border-radius: 999px;
  padding: 0.45rem 0.4rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  color: #6b7a9e;
  background: transparent;
  transition:
    color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
  line-height: 1.2;
}
.segment-btn:hover:not(.is-active) {
  color: #9aa8c4;
  background: rgba(255, 255, 255, 0.04);
}
.segment-btn.is-active {
  color: #f0f4ff;
  background: linear-gradient(180deg, #4f65d4 0%, #3b4db8 100%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}
.sidebar-mid-scroll {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 0.1rem 0.2rem 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(75, 95, 160, 0.45) rgba(12, 14, 22, 0.35);
}
.sidebar-mid-scroll::-webkit-scrollbar {
  width: 5px;
}
.sidebar-mid-scroll::-webkit-scrollbar-track {
  background: rgba(10, 12, 20, 0.55);
  border-radius: 6px;
}
.sidebar-mid-scroll::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(90, 110, 190, 0.55), rgba(60, 75, 150, 0.5));
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.2);
}
.sidebar-mid-scroll::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(110, 130, 210, 0.65), rgba(75, 95, 180, 0.55));
}
.sidebar-mid-page {
  min-height: 0;
}
.sidebar-empty--in-tab {
  padding: 0.6rem 0.25rem 0.4rem;
  text-align: center;
}
.sidebar-empty-hint {
  font-size: 0.8rem;
  color: var(--muted, #8899cc);
  margin: 0.35rem 0 0;
  line-height: 1.45;
}

.sidebar.collapsed {
  width: 36px;
  min-width: 36px;
  padding: 0.75rem 0.3rem;
}

.sidebar-toggle {
  position: absolute;
  top: 8px;
  right: 6px;
  background: none;
  border: none;
  color: var(--muted, #8899cc);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
}

.sidebar-section {
  padding: 0.5rem;
  border-bottom: 1px solid var(--border, #2e3450);
  padding-bottom: 0.75rem;
}

.sidebar-heading {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted, #8899cc);
  margin: 0 0 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-label {
  font-size: 0.75rem;
  color: var(--muted, #8899cc);
  text-align: center;
  margin: 0.15rem 0 0;
}

/* 进度环 */
.progress-ring-wrap {
  position: relative;
  width: 48px;
  height: 48px;
  margin: 0 auto;
}
.progress-ring {
  width: 48px;
  height: 48px;
}
.progress-pct {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text, #e0e6f7);
}

/* 今日任务：卡片分块，长文最多 5 行 + 整段 title 悬停可看全 */
.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.task-card {
  list-style: none;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 100, 0.45);
  background: linear-gradient(145deg, rgba(24, 28, 48, 0.96) 0%, rgba(16, 19, 32, 0.92) 100%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}
.task-card:hover {
  border-color: rgba(91, 114, 232, 0.4);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.task-card.is-done {
  opacity: 0.78;
  border-color: rgba(55, 80, 65, 0.35);
}
.task-card__row {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  padding: 0.48rem 0.5rem 0.52rem;
}
.task-card__num {
  flex-shrink: 0;
  min-width: 1.1rem;
  height: 1.1rem;
  line-height: 1.1rem;
  text-align: center;
  font-size: 0.62rem;
  font-weight: 700;
  color: #93b4f0;
  background: rgba(59, 77, 184, 0.3);
  border-radius: 5px;
  margin-top: 0.04rem;
}
.task-card__check {
  flex-shrink: 0;
  width: 0.95rem;
  height: 0.95rem;
  margin-top: 0.1rem;
  border: 1.5px solid rgba(91, 114, 232, 0.7);
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.2);
  color: #4ade80;
  font-size: 0.58rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.task-card__check.tick {
  background: rgba(34, 197, 94, 0.2);
  border-color: #22c55e;
}
.task-card__main {
  min-width: 0;
  flex: 1;
}
.task-card__desc {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: #e2e8f4;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
  overflow: hidden;
  word-break: break-word;
}
.task-card.is-done .task-card__desc {
  text-decoration: line-through;
  color: #98a0b5;
}
.task-card__meta {
  margin: 0.3rem 0 0;
  font-size: 0.63rem;
  color: #7a8aa8;
  letter-spacing: 0.02em;
}
.task-stat-bar {
  margin-top: 0.45rem;
  padding: 0.32rem 0.45rem;
  text-align: center;
  font-size: 0.66rem;
  line-height: 1.4;
  color: #9aa6bf;
  background: rgba(6, 8, 16, 0.45);
  border-radius: 8px;
  border: 1px solid rgba(48, 56, 80, 0.45);
}
.task-stat-dot {
  display: inline-block;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #5c6a88;
  margin: 0 0.4rem;
  vertical-align: middle;
}

/* 大纲章节：与任务同系卡片，序号圆点 + 5 行内预览 */
.chapter-cards {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.chapter-card {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  margin: 0;
  padding: 0.48rem 0.5rem 0.52rem;
  border-radius: 8px;
  border: 1px solid rgba(52, 60, 88, 0.4);
  background: linear-gradient(150deg, rgba(20, 24, 42, 0.95) 0%, rgba(14, 16, 28, 0.9) 100%);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
.chapter-card__num {
  flex-shrink: 0;
  width: 1.15rem;
  height: 1.15rem;
  line-height: 1.15rem;
  text-align: center;
  font-size: 0.6rem;
  font-weight: 700;
  color: #9eb5dc;
  background: rgba(70, 90, 140, 0.2);
  border-radius: 50%;
  margin-top: 0.12rem;
}
.chapter-card__text {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 0.74rem;
  line-height: 1.5;
  color: #c8d2e8;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
  overflow: hidden;
  word-break: break-word;
}

/* 空状态 */
.sidebar-empty {
  text-align: center;
  font-size: 0.82rem;
  color: var(--muted, #8899cc);
  padding: 0.5rem;
}
.sidebar-empty p {
  margin: 0.2rem 0;
}

/* 快捷跳转 */
.sidebar-shortcuts {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.shortcut-btn {
  display: block;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border, #2e3450);
  border-radius: 6px;
  color: var(--muted, #8899cc);
  font-size: 0.78rem;
  text-decoration: none;
  transition: border-color 0.15s, color 0.15s;
  text-align: center;
}
.shortcut-btn:hover {
  border-color: #5b72e8;
  color: #8ab4f8;
}

/* ── 主对话区（仅消息区内部滚动，占满一屏内剩余列高） */
.chat-pane {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0.5rem 0.75rem 0.5rem;
  gap: 0;
}

.intent-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  margin-bottom: 8px;
  background: var(--card-bg, #1e2233);
  border-radius: 8px;
  border: 1px solid #3b4db8;
}
.intent-badge {
  background: #3b4db8;
  color: #fff;
  border-radius: 10px;
  padding: 2px 10px;
  font-size: 0.75rem;
  font-weight: 600;
}
.intent-thinking {
  font-size: 0.78rem;
  color: var(--muted, #8899cc);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.messages-container {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.9rem 0.75rem;
  background: linear-gradient(165deg, rgba(14, 16, 26, 0.98) 0%, rgba(10, 12, 20, 0.99) 100%);
  border: 1px solid rgba(45, 55, 85, 0.5);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  margin-bottom: 0.45rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  scrollbar-width: thin;
  scrollbar-color: rgba(75, 95, 160, 0.5) rgba(10, 12, 20, 0.4);
}
.messages-container::-webkit-scrollbar {
  width: 5px;
}
.messages-container::-webkit-scrollbar-track {
  background: rgba(8, 10, 16, 0.6);
  border-radius: 6px;
  margin: 4px 0;
}
.messages-container::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(95, 115, 200, 0.55), rgba(65, 80, 150, 0.5));
  border-radius: 6px;
  border: 1px solid rgba(0, 0, 0, 0.25);
}
.messages-container::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(115, 135, 220, 0.65), rgba(80, 100, 180, 0.55));
}

.message-row {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
}
.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  font-size: 1.3rem;
  flex-shrink: 0;
  margin-top: 2px;
}

.bubble-wrapper {
  max-width: 78%;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.message-row.user .bubble-wrapper {
  align-items: flex-end;
}

.action-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.action-badge {
  background: var(--card-bg, #1e2233);
  color: var(--muted, #8899cc);
  border: 1px solid var(--border, #2e3450);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 0.7rem;
}

.bubble {
  padding: 0.65rem 0.95rem;
  border-radius: 12px;
  line-height: 1.65;
  word-break: break-word;
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  color: var(--text, #e0e6f7);
  font-size: 0.9rem;
  white-space: pre-wrap;
}
/* 流结束：v-html 内 <br>，不保留 pre-wrap */
.bubble:not(.streaming) {
  white-space: normal;
}
/* 流式中纯文本 + 保留模型换行 */
.bubble.stream-plain {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.bubble .stream-text {
  white-space: inherit;
}
.message-row.user .bubble {
  background: #3b4db8;
  color: #fff;
  border-color: #3b4db8;
}
.bubble.streaming {
  border-color: #5b72e8;
}
/* Markdown 经 v-html 注入，须 :deep 才能命中子节点 */
.bubble :deep(h1),
.bubble :deep(h2),
.bubble :deep(h3) {
  font-weight: 700;
  margin: 0.6em 0 0.2em;
  color: var(--text, #e0e6f7);
}
.bubble :deep(h1) { font-size: 1.15em; }
.bubble :deep(h2) { font-size: 1.08em; }
.bubble :deep(h3) { font-size: 1.0em; }
.bubble :deep(.bubble-md-line) {
  margin: 0.2em 0;
}
.bubble :deep(strong) { font-weight: 700; }
.bubble :deep(em) { font-style: italic; }
.bubble :deep(code) {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  padding: 0 4px;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.85em;
  color: #93c5fd;
}
.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #8ab4f8;
}
@keyframes blink { 50% { opacity: 0; } }

.loading-row {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}
.loading-dots {
  display: flex;
  gap: 5px;
  padding: 0.6rem 0.9rem;
}
.loading-dots span {
  width: 7px;
  height: 7px;
  background: #5b72e8;
  border-radius: 50%;
  animation: dot-bounce 1.2s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-5px); opacity: 1; }
}

/* ── 底部：快捷指令 + 输入 + 发送（统一卡片） */
.chat-composer {
  flex-shrink: 0;
  margin-top: 0.1rem;
  padding: 0.5rem 0.65rem 0.6rem;
  background: linear-gradient(180deg, rgba(20, 23, 36, 0.55) 0%, rgba(16, 18, 30, 0.98) 100%);
  border: 1px solid rgba(48, 58, 88, 0.45);
  border-radius: 12px;
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.quick-commands {
  padding: 0.1rem 0 0.4rem;
  border: none;
}
.quick-commands-track {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.45rem;
  overflow-x: auto;
  padding: 0.1rem 0 0.15rem;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.quick-commands-track::-webkit-scrollbar {
  display: none;
  height: 0;
}
.quick-ico {
  margin-right: 0.1rem;
  opacity: 0.95;
}
.quick-btn {
  flex-shrink: 0;
  background: rgba(30, 36, 58, 0.55);
  border: 1px solid rgba(65, 80, 120, 0.35);
  color: #a8c4f0;
  border-radius: 999px;
  padding: 0.4rem 0.75rem 0.45rem;
  font-size: 0.76rem;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s,
    box-shadow 0.15s,
    opacity 0.15s;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
.quick-btn:hover:not(:disabled) {
  background: rgba(50, 58, 95, 0.55);
  border-color: rgba(91, 114, 232, 0.45);
  color: #d0e0ff;
}
.quick-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input-area {
  width: 100%;
  padding-top: 0.2rem;
  border: none;
}
.input-field-wrap {
  position: relative;
  width: 100%;
  display: block;
}
.input-box {
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-height: 2.8rem;
  /* 为右下角圆形按钮留空，避免文字压在按钮上 */
  padding: 0.6rem 3.1rem 0.6rem 0.9rem;
  background: rgba(8, 10, 18, 0.92);
  border: 1px solid rgba(50, 62, 95, 0.55);
  border-radius: 10px;
  color: var(--text, #e0e6f7);
  font-size: 0.9rem;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.18);
}
.input-box::placeholder {
  color: #6b7a9e;
}
.input-box:focus {
  outline: none;
  border-color: rgba(91, 114, 232, 0.75);
  box-shadow:
    0 0 0 2px rgba(59, 77, 184, 0.25),
    inset 0 2px 4px rgba(0, 0, 0, 0.12);
}
.input-box:disabled {
  opacity: 0.55;
}
/* 内嵌在输入框右下：灰青蓝圆 + 浅灰向上箭头；停止为暗红圆 + 方块 */
.input-embed-btn {
  position: absolute;
  right: 0.45rem;
  bottom: 0.45rem;
  z-index: 1;
  width: 2.2rem;
  height: 2.2rem;
  padding: 0;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  transition: background 0.15s, transform 0.1s, opacity 0.15s;
}
.input-embed-btn:active:not(:disabled) {
  transform: scale(0.95);
}
.input-embed-ico {
  width: 1.15rem;
  height: 1.15rem;
  display: block;
}
.input-embed-btn--send {
  background: #4a5568;
  color: #c5cedd;
}
.input-embed-btn--send:hover:not(:disabled) {
  background: #556b82;
  color: #f0f4fa;
}
.input-embed-btn--send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.input-embed-btn--stop {
  background: #5c3d42;
  color: #e8c4c4;
}
.input-embed-btn--stop:hover {
  background: #6b484e;
  color: #fff;
}
</style>


