<script setup lang="ts">
import { ref } from 'vue'
import { getTodayPlan, type DailyPlanResponse } from '@/lib/api'

const goal = ref('今天学习 LangGraph 状态机与工具调用')
const loading = ref(false)
const error = ref('')
const plan = ref<DailyPlanResponse | null>(null)

async function onLoad() {
  error.value = ''
  plan.value = null
  loading.value = true
  try {
    plan.value = await getTodayPlan(goal.value.trim())
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <h1>每日学习计划</h1>
    <p class="lead">调用 Java <code>GET /api/plan/today?goal=...</code>（含缓存、数据库与熔断降级）。</p>

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
      <h2>{{ plan.plan_title }}</h2>
      <ol style="margin: 0; padding-left: 1.25rem">
        <li v-for="t in plan.tasks" :key="t.task_id" style="margin-bottom: 0.75rem">
          <strong>#{{ t.task_id }}</strong> {{ t.description }}
          <div style="font-size: 0.85rem; color: var(--muted)">
            预计：{{ t.estimated_time }} · 状态：{{ t.status }}
          </div>
        </li>
      </ol>
    </div>
  </div>
</template>
