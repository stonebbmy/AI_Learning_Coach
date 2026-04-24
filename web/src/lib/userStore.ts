import { reactive, readonly } from 'vue'

const LS_KEY = 'ai_coach_user_id'
const LS_OUTLINE_KEY = 'ai_coach_outline_id'
const LS_PLAN_KEY = 'ai_coach_plan_id'

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

const _state = reactive({
  userId: loadUserId(),
  currentOutlineId: (() => {
    try { return Number(localStorage.getItem(LS_OUTLINE_KEY)) || null } catch { return null }
  })() as number | null,
  currentPlanId: (() => {
    try { return Number(localStorage.getItem(LS_PLAN_KEY)) || null } catch { return null }
  })() as number | null,
})

export const userStore = {
  state: readonly(_state),

  setOutlineId(id: number | null) {
    _state.currentOutlineId = id
    try {
      if (id != null) localStorage.setItem(LS_OUTLINE_KEY, String(id))
      else localStorage.removeItem(LS_OUTLINE_KEY)
    } catch { /* ignore */ }
  },

  setPlanId(id: number | null) {
    _state.currentPlanId = id
    try {
      if (id != null) localStorage.setItem(LS_PLAN_KEY, String(id))
      else localStorage.removeItem(LS_PLAN_KEY)
    } catch { /* ignore */ }
  },

  resetUser() {
    const newId = generateUserId()
    _state.userId = newId
    _state.currentOutlineId = null
    _state.currentPlanId = null
    try {
      localStorage.setItem(LS_KEY, newId)
      localStorage.removeItem(LS_OUTLINE_KEY)
      localStorage.removeItem(LS_PLAN_KEY)
    } catch { /* ignore */ }
  },
}
