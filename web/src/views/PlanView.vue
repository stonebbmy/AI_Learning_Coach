<script setup lang="ts">
import { ref, onMounted, onActivated, computed, watch } from 'vue'
import {
  getTodayPlan,
  isNoTodayPlanError,
  deleteTodayPlanApi,
  updateTaskStatus,
  updateTutorContext,
  type DailyPlanResponse,
} from '@/lib/api'
import { userStore } from '@/lib/userStore'
import LearningModuleShell from '@/components/LearningModuleShell.vue'
import LearningContextHeader from '@/components/LearningContextHeader.vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const goal = ref('')
const loading = ref(false)
const error = ref('')
const routeHint = ref('')
const noPlanToday = ref(false)
const plan = ref<(DailyPlanResponse & { id?: number }) | null>(null)
const updatingTaskId = ref<number | null>(null)
const deleteLoading = ref(false)
const actionLoading = ref(false)

const statusOptions = ['待开始', '进行中', '已完成']

const hasCurrentOutline = computed(
  () => userStore.state.currentOutlineId != null,
)

const displayGoal = computed(() => (plan.value?.source_goal?.trim() ? plan.value.source_goal : goal.value))

const alignment = computed(() => {
  if (!plan.value) return null
  const o = userStore.state.currentOutlineId
  const g = goal.value.trim()
  if (!g) return null
  const so = plan.value.source_outline_id
  const sg = (plan.value.source_goal ?? '').trim()
  const oMatch = (o == null && (so == null || so === undefined)) || o === so
  const gMatch = g === sg
  if (oMatch && gMatch) return 'ok' as const
  return 'stale' as const
})

/** 非空，供「新建」与「重新生成」调用 */
function effectiveCreateGoal(): string {
  const t = goal.value.trim()
  if (t) return t
  const ch0 = userStore.state.outlineChapters[0]
  if (ch0) return `今天学习：${ch0}`
  return '今日学习'
}

function isTaskPending(status: string): boolean {
  const s = (status || '').trim()
  return s === '待开始' || s === '' || s === 'TODO' || s === 'pending'
}

function hasAnyTaskProgress(tasks: { status: string }[] | undefined): boolean {
  if (!tasks?.length) return false
  return tasks.some((t) => !isTaskPending(t.status))
}

function applyContextFromStore() {
  const ch0 = userStore.state.outlineChapters[0]
  if (ch0) {
    goal.value = `今天学习：${ch0}`
  }
}

function applyRouteContext() {
  routeHint.value = ''
  if (String(route.query.fromOutline || '') === '1') {
    applyContextFromStore()
    if (userStore.state.outlineChapters.length) {
      routeHint.value = '已根据「当前大纲」的章节名预填今日目标；可直接点「生成今日计划」或先修改目标。'
    } else {
      routeHint.value = '已从大纲进入计划页。若章节未同步，请在大纲页重新「设为当前」。'
    }
    void router.replace({ path: '/plan' }).catch(() => {
      /* 忽略 */
    })
  }
}

function clearPlanContext() {
  userStore.setPlanId(null)
  userStore.setPlanTasks([])
  userStore.setProgressRate(0)
  void updateTutorContext({
    currentPlanId: null,
    planTasks: [],
  }).catch(() => {
    /* 忽略 */
  })
}

function applyResultToStore(result: DailyPlanResponse) {
  if (result.id) {
    userStore.setPlanId(result.id)
  }
  userStore.setPlanTasks(result.tasks)
  const doneCount = result.tasks.filter((t) =>
    ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
  ).length
  userStore.setProgressRate(result.tasks.length > 0 ? doneCount / result.tasks.length : 0)
  void updateTutorContext({
    currentPlanId: result.id ?? null,
    planTasks: result.tasks.map((t) => ({
      description: t.description,
      status: t.status,
    })),
  }).catch(() => {
    /* 忽略 */
  })
}

/** 有当前大纲时：进页拉库或 404。无当前大纲不请求，不假装已有计划。 */
async function fetchAuto() {
  error.value = ''
  if (!hasCurrentOutline.value) {
    plan.value = null
    noPlanToday.value = true
    return
  }
  noPlanToday.value = false
  loading.value = true
  try {
    const result = await getTodayPlan('', userStore.state.currentOutlineId, { regenerate: false })
    plan.value = result
    if (result.source_goal) {
      goal.value = result.source_goal
    } else {
      applyContextFromStore()
    }
    noPlanToday.value = false
    applyResultToStore(result)
  } catch (e) {
    if (isNoTodayPlanError(e)) {
      plan.value = null
      noPlanToday.value = true
      applyContextFromStore()
    } else {
      error.value = e instanceof Error ? e.message : String(e)
      plan.value = null
    }
  } finally {
    loading.value = false
  }
}

/** 有纲且无今日行：生成 */
async function onCreateTodayPlan() {
  if (!hasCurrentOutline.value) {
    error.value = '请先在「学习大纲」中设一条当前大纲，再回到本页生成。'
    return
  }
  error.value = ''
  noPlanToday.value = false
  const g = effectiveCreateGoal()
  actionLoading.value = true
  try {
    const result = await getTodayPlan(g, userStore.state.currentOutlineId, { regenerate: false })
    plan.value = result
    if (result.source_goal) goal.value = result.source_goal
    applyResultToStore(result)
  } catch (e) {
    if (isNoTodayPlanError(e)) {
      error.value = '仍无今日计划，请稍后再试或检查网络。'
    } else {
      error.value = e instanceof Error ? e.message : String(e)
    }
  } finally {
    actionLoading.value = false
  }
}

function replanGoalString(): string {
  const t = goal.value.trim()
  if (t) return t
  const sg = (plan.value?.source_goal ?? '').trim()
  if (sg) return sg
  return effectiveCreateGoal()
}

/** 已有日计划时：重新生成（不先清空 plan，避免丢 goal / 白屏） */
async function onRegenerateToday() {
  if (!hasCurrentOutline.value) {
    error.value = '无当前大纲，请先去「学习大纲」设当前。'
    return
  }
  if (hasAnyTaskProgress(plan.value?.tasks)) {
    if (
      !confirm(
        '你已有进行中的或已完成的任务。重新生成将用新任务列表替换「今日计划」，原任务与进度在今日计划上不再保留。确定继续？',
      )
    ) {
      return
    }
  }
  error.value = ''
  const g = replanGoalString()
  actionLoading.value = true
  try {
    const result = await getTodayPlan(g, userStore.state.currentOutlineId, { regenerate: true })
    plan.value = result
    if (result.source_goal) goal.value = result.source_goal
    applyResultToStore(result)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    actionLoading.value = false
  }
}

async function onStatusChange(dbId: number | undefined, newStatus: string) {
  if (!dbId) return
  updatingTaskId.value = dbId
  try {
    await updateTaskStatus(dbId, newStatus)
    if (plan.value) {
      const task = plan.value.tasks.find((t) => t.db_id === dbId)
      if (task) task.status = newStatus
      userStore.updateTaskStatus(dbId, newStatus)
      const doneCount = plan.value.tasks.filter((t) =>
        ['已完成', 'done', 'DONE', 'completed'].includes(t.status),
      ).length
      userStore.setProgressRate(
        plan.value.tasks.length > 0 ? doneCount / plan.value.tasks.length : 0,
      )
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    updatingTaskId.value = null
  }
}

async function onDeleteTodayPlan() {
  if (
    !confirm(
      '确定取消并删除「今日计划」及今日全部任务？不可恢复，侧栏会清空当前计划引用。',
    )
  ) {
    return
  }
  deleteLoading.value = true
  error.value = ''
  try {
    await deleteTodayPlanApi()
    plan.value = null
    noPlanToday.value = true
    clearPlanContext()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    deleteLoading.value = false
  }
}

let lastOutlineId = userStore.state.currentOutlineId

onMounted(() => {
  applyContextFromStore()
  lastOutlineId = userStore.state.currentOutlineId
  applyRouteContext()
  void fetchAuto()
})

onActivated(() => {
  applyRouteContext()
})

watch(
  () => userStore.state.currentOutlineId,
  (id) => {
    if (id != null && id !== lastOutlineId) {
      lastOutlineId = id
      applyContextFromStore()
      void fetchAuto()
    } else {
      lastOutlineId = id
      if (id == null) {
        void fetchAuto()
      }
    }
  },
)
</script>

<template>
  <LearningModuleShell>
  <div class="view-plan">
    <div class="view-hero">
      <h1>每日学习计划</h1>
      <p class="lead">
        本页在<strong>已选择当前大纲</strong>时自动加载当天日计划（日期以服务器为准）。「重新生成」<strong>只替换当天的任务与标题</strong>，不修改已保存在「学习大纲」中的大纲内容。
      </p>
    </div>

    <LearningContextHeader :goal-text="displayGoal" />

    <p v-if="routeHint" class="route-hint">{{ routeHint }}</p>
    <p
      v-if="plan && alignment === 'stale' && hasCurrentOutline"
      class="align-warn"
    >
      当前展示的计划是上一次按「大纲 / 目标」生成的；你修改了目标或刚换了当前大纲。请点击「重新生成」以同步今日任务。
    </p>
    <p v-else-if="plan && alignment === 'ok' && hasCurrentOutline" class="align-ok">
      与当前选中的大纲、目标输入一致。
    </p>

    <div v-if="!hasCurrentOutline" class="card empty-box">
      <h2 class="section-title">先设定「当前学习大纲」</h2>
      <p>未选择已保存的当前大纲时，本页无法生成日计划。请在
        <RouterLink to="/outline">学习大纲</RouterLink> 中生成并「设为当前」，再返回本页，即可生成今日计划与任务。
      </p>
      <RouterLink class="cta-link" to="/outline">去「学习大纲」设当前 →</RouterLink>
    </div>

    <template v-else>
      <div v-if="loading && !plan" class="card muted-box state-card">正在加载今日计划…</div>

      <div v-else-if="!plan" class="card empty-box no-plan-block">
        <h2 class="section-title">
          {{ error && !noPlanToday ? '暂时无法加载今日计划' : '今天还没有今日计划' }}
        </h2>
        <p v-if="!(error && !noPlanToday)">
          可填写或沿用下方预填的今日目标，点「生成今日计划」。留空时按首章或默认「今日学习」生成。
        </p>
        <p v-if="error" class="error error-tight">{{ error }}</p>
        <label>今日学习目标（可选）</label>
        <input v-model="goal" type="text" placeholder="留空将使用：首章「今天学习：…」或「今日学习」" />
        <div class="btn-row field-gap">
          <button
            type="button"
            :disabled="actionLoading"
            @click="onCreateTodayPlan"
          >
            {{ actionLoading ? '处理中…' : '生成今日计划' }}
          </button>
        </div>
      </div>

      <template v-else>
        <div class="card plan-actions">
          <label>今日学习目标（重新生成时优先；可空则沿用已保存/首章/默认）</label>
          <input v-model="goal" type="text" placeholder="可修改后再点「重新生成」" />

          <div class="btn-row field-gap">
            <button
              type="button"
              :disabled="actionLoading"
              @click="onRegenerateToday"
            >
              {{ actionLoading ? '处理中…' : '重新生成' }}
            </button>
            <button
              type="button"
              class="secondary danger-ghost"
              :disabled="deleteLoading"
              @click="onDeleteTodayPlan"
            >
              {{ deleteLoading ? '处理中…' : '取消今日计划' }}
            </button>
          </div>
          <p v-if="error" class="error error--block">{{ error }}</p>
        </div>

        <div class="card plan-tasks-card">
        <div class="plan-title-row">
          <h2 class="plan-title">{{ plan.plan_title }}</h2>
          <span v-if="plan.id" class="plan-id">计划 #{{ plan.id }}</span>
        </div>

        <ol class="plan-task-list">
          <li v-for="t in plan.tasks" :key="t.task_id" class="plan-task-item">
            <div class="plan-task-body">
              <div class="plan-task-main">
                <strong>#{{ t.task_id }}</strong> {{ t.description }}
                <div class="plan-task-meta">预计：{{ t.estimated_time }}</div>
              </div>
              <div v-if="t.db_id" class="plan-task-select">
                <select
                  :value="t.status"
                  class="select-inline"
                  :disabled="updatingTaskId === t.db_id"
                  @change="onStatusChange(t.db_id, ($event.target as HTMLSelectElement).value)"
                >
                  <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
                </select>
              </div>
              <div v-else class="plan-status-fallback">{{ t.status }}</div>
            </div>
          </li>
        </ol>

        <div v-if="userStore.state.currentPlanId" class="plan-saved-hint">
          已保存，侧栏可展示任务，也可回私教继续。
        </div>
        <p v-if="plan" class="plan-footer-links">
          <RouterLink to="/progress">查看总进度</RouterLink>
          <span class="link-sep">·</span>
          <RouterLink to="/">回 AI 私教</RouterLink>
        </p>
        </div>
      </template>
    </template>
  </div>
  </LearningModuleShell>
</template>

<style scoped>
.btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
  align-items: center;
}
.muted-box {
  color: var(--muted, #8899cc);
  font-size: 0.95rem;
}
.empty-box {
  border: 1px solid rgba(91, 114, 232, 0.35);
  background: rgba(15, 17, 26, 0.6);
}
.empty-box p {
  line-height: 1.55;
  color: var(--text, #e0e6f7);
  margin: 0.5rem 0 1rem;
}
.cta-link {
  display: inline-block;
  color: #8ab4f8;
  font-weight: 600;
}
.error-box {
  border-color: #b91c1c;
}
.danger-ghost {
  color: #fecaca;
  border-color: rgba(127, 29, 29, 0.6);
  background: rgba(69, 10, 10, 0.35);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 4px 10px;
  border-radius: 6px;
}
.route-hint {
  margin: 0 0 0.9rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #7dd3a8;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.align-ok {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  line-height: 1.4;
  color: var(--muted, #8899cc);
}
.align-warn {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  line-height: 1.4;
  color: #fbbf24;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.3);
}
.error-tight {
  margin: 0.5rem 0 0.75rem;
}
.error--block {
  margin-top: 0.75rem;
}
.plan-tasks-card .section-title,
.plan-tasks-card h2.plan-title {
  color: var(--text);
}
.plan-title-row {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin: 0;
}
.plan-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text);
}
.plan-id {
  font-size: 0.8rem;
  color: var(--muted);
}
.plan-task-list {
  margin: 1rem 0 0;
  padding-left: 1.25rem;
}
.plan-task-item {
  margin-bottom: 1rem;
}
.plan-task-item:last-child {
  margin-bottom: 0;
}
.plan-task-body {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.plan-task-main {
  flex: 1;
  min-width: 10rem;
}
.plan-task-meta {
  font-size: 0.85rem;
  color: var(--muted);
  margin-top: 0.25rem;
}
.plan-task-select {
  flex-shrink: 0;
}
.plan-status-fallback {
  font-size: 0.85rem;
  color: var(--muted);
  flex-shrink: 0;
}
.plan-saved-hint {
  margin-top: 1rem;
  font-size: 0.85rem;
  color: var(--muted);
}
.plan-footer-links {
  margin: 1.25rem 0 0;
}
.link-sep {
  margin: 0 0.35rem;
  color: var(--muted);
}
</style>
