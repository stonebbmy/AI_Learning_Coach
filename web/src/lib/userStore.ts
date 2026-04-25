import { reactive, readonly } from 'vue'

const LS_KEY = 'ai_coach_user_id'
const LS_OUTLINE_KEY = 'ai_coach_outline_id'
const LS_PLAN_KEY = 'ai_coach_plan_id'
const LS_CHAPTERS_KEY = 'ai_coach_outline_chapters'
const LS_TASKS_KEY = 'ai_coach_plan_tasks'
const LS_PROGRESS_KEY = 'ai_coach_progress_rate'

function generateUserId(): string {
  return 'user_' + Math.random().toString(36).slice(2, 10) + '_' + Date.now().toString(36)
}

function loadUserId(): string {
  try {
    const saved = localStorage.getItem(LS_KEY)
    if (saved && saved.trim()) return saved.trim()
    const newId = generateUserId()
    localStorage.setItem(LS_KEY, newId)
    return newId
  } catch {
    return generateUserId()
  }
}

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export interface PlanTask {
  task_id: number
  db_id?: number
  description: string
  estimated_time: string
  status: string
}

const _state = reactive({
  userId: loadUserId(),
  currentOutlineId: (() => {
    try {
      return Number(localStorage.getItem(LS_OUTLINE_KEY)) || null
    } catch {
      return null
    }
  })() as number | null,
  currentPlanId: (() => {
    try {
      return Number(localStorage.getItem(LS_PLAN_KEY)) || null
    } catch {
      return null
    }
  })() as number | null,
  // 扩展字段
  outlineChapters: loadJson<string[]>(LS_CHAPTERS_KEY, []),
  planTasks: loadJson<PlanTask[]>(LS_TASKS_KEY, []),
  progressRate: loadJson<number>(LS_PROGRESS_KEY, 0),
})

export const userStore = {
  state: readonly(_state),

  setOutlineId(id: number | null) {
    _state.currentOutlineId = id
    try {
      if (id != null) localStorage.setItem(LS_OUTLINE_KEY, String(id))
      else localStorage.removeItem(LS_OUTLINE_KEY)
    } catch {
      /* ignore */
    }
  },

  setPlanId(id: number | null) {
    _state.currentPlanId = id
    try {
      if (id != null) localStorage.setItem(LS_PLAN_KEY, String(id))
      else localStorage.removeItem(LS_PLAN_KEY)
    } catch {
      /* ignore */
    }
  },

  setOutlineChapters(chapters: string[]) {
    _state.outlineChapters = chapters
    try {
      localStorage.setItem(LS_CHAPTERS_KEY, JSON.stringify(chapters))
    } catch {
      /* ignore */
    }
  },

  setPlanTasks(tasks: PlanTask[]) {
    _state.planTasks = tasks
    try {
      localStorage.setItem(LS_TASKS_KEY, JSON.stringify(tasks))
    } catch {
      /* ignore */
    }
  },

  setProgressRate(rate: number) {
    _state.progressRate = rate
    try {
      localStorage.setItem(LS_PROGRESS_KEY, JSON.stringify(rate))
    } catch {
      /* ignore */
    }
  },

  /** 清除当前今日计划与进度（如删除「当前」大纲、需与侧栏/私教一致时） */
  clearPlanState() {
    this.setPlanId(null)
    this.setPlanTasks([])
    this.setProgressRate(0)
  },

  updateTaskStatus(taskId: number, status: string) {
    const task = _state.planTasks.find((t) => t.task_id === taskId || t.db_id === taskId)
    if (task) {
      ;(task as PlanTask).status = status
      try {
        localStorage.setItem(LS_TASKS_KEY, JSON.stringify(_state.planTasks))
      } catch {
        /* ignore */
      }
    }
  },

  resetUser() {
    const newId = generateUserId()
    _state.userId = newId
    _state.currentOutlineId = null
    _state.currentPlanId = null
    _state.outlineChapters = []
    _state.planTasks = []
    _state.progressRate = 0
    try {
      localStorage.setItem(LS_KEY, newId)
      localStorage.removeItem(LS_OUTLINE_KEY)
      localStorage.removeItem(LS_PLAN_KEY)
      localStorage.removeItem(LS_CHAPTERS_KEY)
      localStorage.removeItem(LS_TASKS_KEY)
      localStorage.removeItem(LS_PROGRESS_KEY)
    } catch {
      /* ignore */
    }
  },
}
