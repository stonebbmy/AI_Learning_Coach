<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchProgressSummary, type ProgressSummary } from '@/lib/api'
import { userStore } from '@/lib/userStore'

const loading = ref(false)
const error = ref('')
const summary = ref<ProgressSummary | null>(null)

async function loadSummary() {
  loading.value = true
  error.value = ''
  try {
    summary.value = await fetchProgressSummary()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadSummary)

function pct(val: number) {
  return (val * 100).toFixed(0) + '%'
}

function barColor(rate: number) {
  if (rate >= 0.8) return '#22c55e'
  if (rate >= 0.4) return '#f59e0b'
  return '#ef4444'
}
</script>

<template>
  <div>
    <h1>学习进度</h1>
    <p class="lead">
      汇总当前用户（{{ userStore.state.userId.slice(0, 12) }}…）的历史学习计划完成情况。
    </p>

    <div v-if="loading" class="card">加载中…</div>
    <div v-else-if="error" class="card"><p class="error">{{ error }}</p></div>

    <div v-else-if="summary" class="card">
      <div style="display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 1.5rem">
        <div style="text-align: center">
          <div style="font-size: 2rem; font-weight: 700; color: var(--accent)">
            {{ pct(summary.completionRate) }}
          </div>
          <div style="color: var(--muted); font-size: 0.9rem">总体完成率</div>
        </div>
        <div style="text-align: center">
          <div style="font-size: 2rem; font-weight: 700">{{ summary.doneTasks }}</div>
          <div style="color: var(--muted); font-size: 0.9rem">已完成任务</div>
        </div>
        <div style="text-align: center">
          <div style="font-size: 2rem; font-weight: 700">{{ summary.totalTasks }}</div>
          <div style="color: var(--muted); font-size: 0.9rem">总任务数</div>
        </div>
      </div>

      <div
        style="height: 12px; border-radius: 6px; background: var(--border); overflow: hidden; margin-bottom: 1.5rem"
      >
        <div
          :style="{
            width: pct(summary.completionRate),
            height: '100%',
            background: barColor(summary.completionRate),
            transition: 'width 0.6s ease',
          }"
        />
      </div>

      <h3 style="margin-bottom: 0.75rem">按日明细</h3>
      <div v-if="summary.chapterStats && summary.chapterStats.length === 0" style="color: var(--muted)">
        暂无历史计划记录
      </div>
      <table v-else style="width: 100%; border-collapse: collapse; font-size: 0.9rem">
        <thead>
          <tr style="border-bottom: 1px solid var(--border)">
            <th style="text-align: left; padding: 0.4rem 0.5rem">日期 / 计划</th>
            <th style="text-align: center; padding: 0.4rem 0.5rem">已完成</th>
            <th style="text-align: center; padding: 0.4rem 0.5rem">总任务</th>
            <th style="text-align: left; padding: 0.4rem 0.5rem">完成率</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(s, i) in (summary as any).dailyStats || []"
            :key="i"
            style="border-bottom: 1px solid var(--border)"
          >
            <td style="padding: 0.5rem">
              <div style="font-weight: 600">{{ s.planDate }}</div>
              <div style="color: var(--muted); font-size: 0.85rem">{{ s.planTitle }}</div>
            </td>
            <td style="text-align: center; padding: 0.5rem">{{ s.done }}</td>
            <td style="text-align: center; padding: 0.5rem">{{ s.total }}</td>
            <td style="padding: 0.5rem; min-width: 120px">
              <div style="display: flex; align-items: center; gap: 0.5rem">
                <div
                  style="flex: 1; height: 8px; border-radius: 4px; background: var(--border); overflow: hidden"
                >
                  <div
                    :style="{
                      width: pct(s.completionRate),
                      height: '100%',
                      background: barColor(s.completionRate),
                    }"
                  />
                </div>
                <span style="font-size: 0.8rem; color: var(--muted); width: 36px; text-align: right">
                  {{ pct(s.completionRate) }}
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="card" style="color: var(--muted)">暂无进度数据，请先生成并完成每日计划。</div>

    <div style="margin-top: 1rem">
      <button type="button" class="secondary" @click="loadSummary">刷新</button>
    </div>
  </div>
</template>
