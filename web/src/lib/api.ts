/**
 * 开发环境走 Vite proxy，避免跨域；生产可设 VITE_JAVA_BASE / VITE_AI_BASE。
 */
import { userStore } from './userStore'

const dev = import.meta.env.DEV

export const javaBase = dev
  ? '/proxy-java'
  : (import.meta.env.VITE_JAVA_BASE as string) || 'http://localhost:8080'

export const aiBase = dev
  ? '/proxy-ai'
  : (import.meta.env.VITE_AI_BASE as string) || '/proxy-ai'

/** 获取含 userId 的通用请求头 */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    'X-User-Id': userStore.state.userId,
    ...extra,
  }
}

export interface OutlineChapter {
  chapter_title: string
  description: string
  key_points: string[]
}

export interface OutlineGenerateResponse {
  title: string
  overview: string
  chapters: OutlineChapter[]
}

export async function generateOutline(
  target: string,
  deadline: string
): Promise<OutlineGenerateResponse> {
  const r = await fetch(`${aiBase}/outline/generate`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ target, deadline }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json()
}

/** 转为 Java /api/outline/confirm 所需 camelCase */
export function toOutlineConfirmBody(o: OutlineGenerateResponse) {
  return {
    title: o.title,
    overview: o.overview,
    chapters: o.chapters.map((c) => ({
      chapterTitle: c.chapter_title,
      description: c.description,
      keyPoints: c.key_points,
    })),
  }
}

export async function confirmOutline(body: ReturnType<typeof toOutlineConfirmBody>) {
  const r = await fetch(`${javaBase}/api/outline/confirm`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json()
}

/** 后端已确认并持久化的大纲（Java 序列化为 camelCase） */
export interface StudyOutlineListItem {
  id: number
  userId?: string
  title: string
  overview: string
  chapters?: {
    id?: number
    chapterTitle: string
    description?: string
    keyPoints?: string[]
  }[]
}

export async function fetchOutlineList(): Promise<StudyOutlineListItem[]> {
  const r = await fetch(`${javaBase}/api/outline/list`, { headers: authHeaders() })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<StudyOutlineListItem[]>
}

export async function uploadKnowledge(file: File): Promise<{ success: boolean; message: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const userId = userStore.state.userId
  const r = await fetch(`${javaBase}/api/knowledge/upload?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json()
}

export interface KnowledgeSourceItem {
  source: string
  chunk_count: number
  upload_date: string | null
}

export interface KnowledgeSummaryResponse {
  total_chunks: number
  sources: KnowledgeSourceItem[]
}

export async function fetchKnowledgeSummary(): Promise<KnowledgeSummaryResponse> {
  const userId = userStore.state.userId
  const r = await fetch(`${javaBase}/api/knowledge/summary?user_id=${encodeURIComponent(userId)}`, {
    headers: authHeaders(),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<KnowledgeSummaryResponse>
}

export interface KnowledgeChunkItem {
  id: string
  source: string | null
  upload_date: string | null
  text_preview: string
  text_length: number
}

export interface KnowledgeChunksResponse {
  limit: number
  offset: number
  has_more: boolean
  chunks: KnowledgeChunkItem[]
}

export async function fetchKnowledgeChunks(params: {
  source?: string
  limit?: number
  offset?: number
}): Promise<KnowledgeChunksResponse> {
  const q = new URLSearchParams()
  q.set('user_id', userStore.state.userId)
  if (params.source) q.set('source', params.source)
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.offset != null) q.set('offset', String(params.offset))
  const base = javaBase.replace(/\/$/, '')
  const url = `${base}/api/knowledge/chunks?${q.toString()}`
  const r = await fetch(url, { headers: authHeaders() })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<KnowledgeChunksResponse>
}

export interface TaskItem {
  task_id: number
  db_id?: number
  description: string
  estimated_time: string
  status: string
}

export interface DailyPlanResponse {
  plan_title: string
  tasks: TaskItem[]
  id?: number
  /** 生成时使用的已确认大纲 ID，可与当前选中大纲对账 */
  source_outline_id?: number | null
  /** 生成时使用的目标原文 */
  source_goal?: string | null
}

/** 后端 404：今日尚未生成计划且 goal 为空、不应调 AI 时 */
export class NoTodayPlanError extends Error {
  readonly isNoTodayPlan = true
  constructor() {
    super('今日尚无计划')
    this.name = 'NoTodayPlanError'
  }
}

export function isNoTodayPlanError(e: unknown): e is NoTodayPlanError {
  return e instanceof NoTodayPlanError
}

/**
 * 今日计划。`goal` 可空：有当日行时只读；无行且无内容则返回 404（抛 NoTodayPlanError）。
 */
export async function getTodayPlan(
  goal: string = '',
  outlineId?: number | null,
  options?: { regenerate?: boolean },
): Promise<DailyPlanResponse> {
  const q = new URLSearchParams()
  q.set('goal', goal)
  if (outlineId) q.set('outlineId', String(outlineId))
  if (options?.regenerate) q.set('regenerate', 'true')
  const r = await fetch(`${javaBase}/api/plan/today?${q.toString()}`, {
    headers: authHeaders(),
  })
  if (r.status === 404) {
    throw new NoTodayPlanError()
  }
  if (!r.ok) {
    const t = await r.text()
    const err = new Error(t || `服务暂时不可用 (HTTP ${r.status})`) as Error & { status?: number }
    err.status = r.status
    throw err
  }
  const data = (await r.json()) as Record<string, unknown>
  return normalizePlan(data)
}

export async function deleteTodayPlanApi(): Promise<void> {
  const r = await fetch(`${javaBase}/api/plan/today`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
}

export async function deleteOutlineApi(outlineId: number): Promise<void> {
  const r = await fetch(`${javaBase}/api/outline/${outlineId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
}

/** 解析 Spring/Java 返回的 camelCase（若后端统一为 snake 也可兼容） */
export function normalizePlan(data: Record<string, unknown>): DailyPlanResponse {
  const planTitle = (data.planTitle ?? data.plan_title) as string
  const rawTasks = (data.tasks ?? []) as Record<string, unknown>[]
  const tasks = rawTasks.map((t) => ({
    task_id: Number(t.taskId ?? t.task_id),
    db_id: Number(t.id ?? t.db_id ?? 0) || undefined,
    description: String(t.description ?? ''),
    estimated_time: String(t.estimatedTime ?? t.estimated_time ?? ''),
    status: String(t.status ?? ''),
  }))
  const so =
    (data.sourceOutlineId ?? data.source_outline_id) as number | null | undefined
  const sg = (data.sourceGoal ?? data.source_goal) as string | null | undefined
  return {
    id: data.id as number | undefined,
    plan_title: planTitle,
    tasks,
    source_outline_id: so == null || Number.isNaN(Number(so)) ? null : Number(so),
    source_goal: sg ?? null,
  }
}

function extractSseDataPayload(raw: string): string | null {
  const payload = raw.trim()
  if (!payload || payload === '[DONE]') return null
  try {
    const parsed = JSON.parse(payload) as unknown
    if (typeof parsed === 'string') return parsed
    if (parsed && typeof parsed === 'object' && parsed !== null && 'data' in parsed) {
      return String((parsed as { data: unknown }).data ?? '')
    }
  } catch {
    return payload
  }
  return null
}

export async function streamChat(
  question: string,
  sessionId: string,
  onChunk: (text: string) => void,
  signal?: AbortSignal,
  messages?: { role: string; content: string }[],
  planId?: number | null,
): Promise<void> {
  const body: Record<string, unknown> = { question, sessionId }
  if (messages?.length) body.messages = messages
  if (planId) body.planId = planId
  const r = await fetch(`${javaBase}/api/chat`, {
    method: 'POST',
    headers: authHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }),
    body: JSON.stringify(body),
    signal,
  })
  if (!r.ok || !r.body) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }

  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let lineBuf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    lineBuf += dec.decode(value, { stream: true })

    let nl: number
    while ((nl = lineBuf.indexOf('\n')) >= 0) {
      const line = lineBuf.slice(0, nl).replace(/\r$/, '')
      lineBuf = lineBuf.slice(nl + 1)

      if (line.startsWith('data:')) {
        const text = extractSseDataPayload(line.slice(5))
        if (text !== null && text !== '') onChunk(text)
      }
      // sse-starlette 可能发送 event: end，无正文则跳过
      if (line.startsWith('event:')) {
        continue
      }
    }
  }
}

export interface ChatAgentResponse {
  answer: string
  session_id?: string
  sessionId?: string
  request_id?: string
  requestId?: string
}

/**
 * 工具调用 Agent（非流式），经 Java POST /api/chat/agent → Python /api/chat/agent
 */
export async function chatAgent(question: string, sessionId: string): Promise<ChatAgentResponse> {
  const r = await fetch(`${javaBase}/api/chat/agent`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ question, sessionId }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<ChatAgentResponse>
}

// ---------------------------------------------------------------------------
// 可观测性指标（直连 Python AI 服务）
// ---------------------------------------------------------------------------

export interface MetricsCache {
  exact_hit: number
  exact_miss: number
  exact_hit_rate: number
  semantic_hit: number
  semantic_miss: number
  semantic_hit_rate: number
  combined_hit_rate: number
}

export interface MetricsStats {
  timestamp: number
  cache: MetricsCache
  tokens: {
    total_in: number
    total_out: number
    estimated_cost_usd: number
  }
  latency: {
    avg_ms: number
    sample_count: number
  }
  requests: {
    total: number
    error: number
    error_rate: number
  }
  error?: string
}

export async function fetchMetricsStats(): Promise<MetricsStats> {
  const r = await fetch(`${javaBase}/api/metrics/stats`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<MetricsStats>
}

export interface CircuitBreakerStatus {
  state: 'closed' | 'open' | 'half_open'
  failure_count: number
  failure_threshold: number
  reset_timeout_seconds: number
  open_for_seconds?: number
  remaining_cooldown_seconds?: number
}

export async function fetchCircuitBreaker(): Promise<CircuitBreakerStatus> {
  const r = await fetch(`${javaBase}/api/metrics/circuit-breaker`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<CircuitBreakerStatus>
}

export interface SessionTokenUsage {
  session_id: string
  used_tokens: number
  budget: number
  remaining: number
  budget_enabled: boolean
  ttl_seconds: number
  error?: string
}

export async function fetchSessionTokenUsage(sessionId: string): Promise<SessionTokenUsage> {
  const r = await fetch(
    `${javaBase}/api/metrics/session/${encodeURIComponent(sessionId)}`,
    { headers: authHeaders() },
  )
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<SessionTokenUsage>
}

export interface HealthDetail {
  status: string
  services: Record<string, string>
}

export async function fetchHealthDetail(): Promise<HealthDetail> {
  const r = await fetch(`${javaBase}/api/health/detail`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<HealthDetail>
}

// ---------------------------------------------------------------------------
// RAG 质量评估（LLM-as-Judge，直连 Python AI 服务）
// ---------------------------------------------------------------------------

export interface RagEvalScoreItem {
  score: number
  reason: string
}

export interface RagEvalResponse {
  question: string
  answer_preview: string
  context_preview: string
  scores: {
    faithfulness: RagEvalScoreItem
    answer_relevance: RagEvalScoreItem
    context_relevance: RagEvalScoreItem
    overall: number
  }
  interpretation: string
  error?: string
}

export async function evalRag(question: string): Promise<RagEvalResponse> {
  const r = await fetch(`${javaBase}/api/eval/rag`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ question }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<RagEvalResponse>
}

/**
 * 多模态占位探测（经 Java 代理，默认返回 503）
 */
export async function visionProbe(imageUrl: string, question: string): Promise<unknown> {
  const r = await fetch(`${javaBase}/api/chat/vision-probe`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ image_url: imageUrl, question }),
  })
  const text = await r.text()
  try {
    return JSON.parse(text) as unknown
  } catch {
    return { raw: text, status: r.status }
  }
}

/** 更新指定任务状态 */
export async function updateTaskStatus(taskId: number, status: string): Promise<void> {
  const r = await fetch(`${javaBase}/api/task/${taskId}/status`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ status }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
}

export interface DailyPlanStat {
  planId?: number
  planDate: string
  planTitle: string
  done: number
  total: number
  completionRate: number
  tasks?: { id: number; description: string; status: string; done: boolean }[]
}

export interface ProgressSummary {
  userId: string
  totalTasks: number
  doneTasks: number
  completionRate: number
  dailyStats: DailyPlanStat[]
}

/** 获取学习进度汇总 */
export async function fetchProgressSummary(): Promise<ProgressSummary> {
  const r = await fetch(`${javaBase}/api/progress/summary`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<ProgressSummary>
}

// ---------------------------------------------------------------------------
// 智能私教总控层
// ---------------------------------------------------------------------------

export interface TutorCardPayload {
  type: 'outline' | 'plan' | 'quiz'
  payload: Record<string, unknown>
}

export interface TutorSseCallbacks {
  onIntent?: (intent: string) => void
  onActions?: (actions: string[]) => void
  onCard?: (card: TutorCardPayload) => void
  onChunk: (text: string) => void
  onEnd?: () => void
  onError?: (msg: string) => void
}

/**
 * 智能私教 SSE 流式对话。
 * 解析多种 SSE 事件类型：intent / actions / data / end / error
 */
export async function streamTutorChat(
  question: string,
  sessionId: string,
  callbacks: TutorSseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${javaBase}/api/tutor/chat`, {
    method: 'POST',
    headers: authHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }),
    body: JSON.stringify({
      question,
      session_id: sessionId,
    }),
    signal,
  })
  if (!r.ok || !r.body) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }

  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let lineBuf = ''
  let currentEvent = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    lineBuf += dec.decode(value, { stream: true })

    let nl: number
    while ((nl = lineBuf.indexOf('\n')) >= 0) {
      const line = lineBuf.slice(0, nl).replace(/\r$/, '')
      lineBuf = lineBuf.slice(nl + 1)

      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const payload = line.slice(5).trim()
        if (!payload || payload === '[DONE]') {
          currentEvent = ''
          continue
        }

        if (currentEvent === 'intent') {
          callbacks.onIntent?.(payload)
        } else if (currentEvent === 'actions') {
          try {
            const arr = JSON.parse(payload) as string[]
            callbacks.onActions?.(arr)
          } catch { /* ignore */ }
        } else if (currentEvent === 'card') {
          try {
            const card = JSON.parse(payload) as TutorCardPayload
            callbacks.onCard?.(card)
          } catch { /* ignore */ }
        } else if (currentEvent === 'end') {
          callbacks.onEnd?.()
        } else if (currentEvent === 'error') {
          callbacks.onError?.(payload)
        } else {
          let text = payload
          try {
            const parsed = JSON.parse(payload) as unknown
            if (typeof parsed === 'string') text = parsed
          } catch { /* 不是 JSON，直接用原文 */ }
          if (text) callbacks.onChunk(text)
        }
        currentEvent = ''
      }
    }
  }
}

export interface TutorContextPayload {
  currentOutlineId?: number | null
  currentPlanId?: number | null
  activeTopic?: string
  progressRate?: number
  outlineChapters?: string[]
  planTasks?: { description: string; status: string }[]
}

export interface TutorHistoryResponse {
  session_id: string
  messages: { role: string; content: string }[]
  count: number
}

/** 拉取会话历史记录（前端挂载时恢复对话） */
export async function fetchTutorHistory(sessionId: string, limit = 20): Promise<TutorHistoryResponse> {
  const r = await fetch(
    `${javaBase}/api/tutor/history/${encodeURIComponent(sessionId)}?limit=${limit}`,
    { headers: authHeaders() },
  )
  if (!r.ok) return { session_id: sessionId, messages: [], count: 0 }
  return r.json() as Promise<TutorHistoryResponse>
}

/** 同步私教上下文（切换大纲/计划后调用） */
export async function updateTutorContext(payload: TutorContextPayload): Promise<void> {
  const r = await fetch(`${javaBase}/api/tutor/context`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      current_outline_id: payload.currentOutlineId ?? null,
      current_plan_id: payload.currentPlanId ?? null,
      active_topic: payload.activeTopic ?? '',
      progress_rate: payload.progressRate ?? 0,
      outline_chapters: payload.outlineChapters ?? [],
      plan_tasks: payload.planTasks ?? [],
    }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
}
