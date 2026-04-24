<script setup lang="ts">
import { ref } from 'vue'
import { getTodayPlan, updateTaskStatus, updateTutorContext, type DailyPlanResponse } from '@/lib/api'
import { userStore } from '@/lib/userStore'

const goal = ref('今天学习 LangGraph 状态机与工具调用')
const loading = ref(false)
const error = ref('')
const plan = ref<(DailyPlanResponse & { id?: number }) | null>(null)
const updatingTaskId = ref<number | null>(null)

const statusOptions = ['待开始', '进行中', '已完成']

async function onLoad() {
  error.value = ''
  plan.value = null
  loading.value = true
  try {
    const result = await getTodayPlan(goal.value.trim(), userStore.state.currentOutlineId)
    plan.value = result
    if (result.id) {
      userStore.setPlanId(result.id)
    }
    // 同步计划上下文到私教 Redis
    updateTutorContext({
      currentPlanId: result.id ?? null,
      planTasks: result.tasks.map((t) => ({
        description: t.description,
        status: t.status,
      })),
    }).catch(() => { /* 静默失败 */ })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
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
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    updatingTaskId.value = null
  }
}
</script>

<template>
  <div>
    <h1>每日学习计划</h1>
    <p class="lead">
      调用 Java <code>GET /api/plan/today</code>（含缓存、数据库与熔断降级）。
      <span v-if="userStore.state.currentOutlineId" style="color: var(--muted); font-size: 0.9rem">
        · 已关联大纲 #{{ userStore.state.currentOutlineId }}，计划将聚焦大纲章节
      </span>
    </p>

    <div class="card">
      <label>今日学习目标</label>
      <input v-model="goal" type="text" />

      <div style="margin-top: 1rem">
        <button type="button" :disabled="loading || !goal.trim()" @click="onLoad">
          {{ loading ? '加载中…' : '获取今日计划' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="plan" class="card">
      <div style="display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap">
        <h2 style="margin: 0">{{ plan.plan_title }}</h2>
        <span v-if="plan.id" style="font-size: 0.8rem; color: var(--muted)">计划 #{{ plan.id }}</span>
      </div>

      <ol style="margin: 1rem 0 0; padding-left: 1.25rem">
        <li v-for="t in plan.tasks" :key="t.task_id" style="margin-bottom: 1rem">
          <div style="display: flex; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap">
            <div style="flex: 1">
              <strong>#{{ t.task_id }}</strong> {{ t.description }}
              <div style="font-size: 0.85rem; color: var(--muted); margin-top: 0.25rem">
                预计：{{ t.estimated_time }}
              </div>
            </div>
            <div v-if="t.db_id" style="flex-shrink: 0">
              <select
                :value="t.status"
                :disabled="updatingTaskId === t.db_id"
                style="font-size: 0.85rem; padding: 2px 6px; border-radius: 4px"
                @change="onStatusChange(t.db_id, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
              </select>
            </div>
            <div v-else style="font-size: 0.85rem; color: var(--muted)">{{ t.status }}</div>
          </div>
        </li>
      </ol>

      <div v-if="userStore.state.currentPlanId" style="margin-top: 1rem; font-size: 0.85rem; color: var(--muted)">
        计划 ID 已记录（#{{ userStore.state.currentPlanId }}），前往 RAG 问答时将自动注入今日任务上下文。
      </div>
    </div>
  </div>
</template>
