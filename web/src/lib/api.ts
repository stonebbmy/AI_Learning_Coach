/**
 * 开发环境走 Vite proxy，避免跨域；生产可设 VITE_JAVA_BASE / VITE_AI_BASE。
 */
const dev = import.meta.env.DEV

export const javaBase = dev
  ? '/proxy-java'
  : (import.meta.env.VITE_JAVA_BASE as string) || 'http://localhost:8080'

export const aiBase = dev
  ? '/proxy-ai'
  : (import.meta.env.VITE_AI_BASE as string) || 'http://localhost:8000/api'

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
    headers: { 'Content-Type': 'application/json' },
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json()
}

export async function uploadKnowledge(file: File): Promise<{ success: boolean; message: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${aiBase}/knowledge/upload`, {
    method: 'POST',
    body: fd,
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json()
}

export interface TaskItem {
  task_id: number
  description: string
  estimated_time: string
  status: string
}

export interface DailyPlanResponse {
  plan_title: string
  tasks: TaskItem[]
}

export async function getTodayPlan(goal: string): Promise<DailyPlanResponse> {
  const q = encodeURIComponent(goal)
  const r = await fetch(`${javaBase}/api/plan/today?goal=${q}`)
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  const data = (await r.json()) as Record<string, unknown>
  return normalizePlan(data)
}

/** 解析 Spring/Java 返回的 camelCase（若后端统一为 snake 也可兼容） */
export function normalizePlan(data: Record<string, unknown>): DailyPlanResponse {
  const planTitle = (data.planTitle ?? data.plan_title) as string
  const rawTasks = (data.tasks ?? []) as Record<string, unknown>[]
  const tasks = rawTasks.map((t) => ({
    task_id: Number(t.taskId ?? t.task_id),
    description: String(t.description ?? ''),
    estimated_time: String(t.estimatedTime ?? t.estimated_time ?? ''),
    status: String(t.status ?? ''),
  }))
  return { plan_title: planTitle, tasks }
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
  /** 可选：显式多轮历史；不传则完全依赖后端按 sessionId 存 Redis 的短期记忆 */
  messages?: { role: string; content: string }[]
): Promise<void> {
  const body: Record<string, unknown> = { question, sessionId }
  if (messages?.length) body.messages = messages
  const r = await fetch(`${javaBase}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, sessionId }),
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(t || `HTTP ${r.status}`)
  }
  return r.json() as Promise<ChatAgentResponse>
}

/**
 * 多模态占位探测（直连 Python，默认返回 503）
 */
export async function visionProbe(imageUrl: string, question: string): Promise<unknown> {
  const r = await fetch(`${aiBase}/chat/vision-probe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_url: imageUrl, question }),
  })
  const text = await r.text()
  try {
    return JSON.parse(text) as unknown
  } catch {
    return { raw: text, status: r.status }
  }
}
