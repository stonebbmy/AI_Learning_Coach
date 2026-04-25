<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchProgressSummary, type ProgressSummary } from '@/lib/api'
import { userStore } from '@/lib/userStore'
import LearningModuleShell from '@/components/LearningModuleShell.vue'

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

const hasDaily = computed(
  () => summary.value && summary.value.dailyStats && summary.value.dailyStats.length > 0,
)

const expanded = ref<number | null>(null)

function toggleRow(i: number) {
  expanded.value = expanded.value === i ? null : i
}

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
  <LearningModuleShell>
  <div class="view-progress">
    <div class="view-hero">
      <h1>学习进度</h1>
      <p class="lead">
        按历史「每日计划」汇总任务完成率（用户 {{ userStore.state.userId.slice(0, 12) }}…）。完成与更新任务请在大纲/计划页或私教侧栏操作。
      </p>
    </div>

    <div v-if="loading" class="card state-card">加载中…</div>
    <div v-else-if="error" class="card"><p class="error">{{ error }}</p></div>

    <div v-else-if="summary" class="card">
      <div class="stat-grid">
        <div class="stat-tile stat-tile--accent">
          <div class="stat-value">{{ pct(summary.completionRate) }}</div>
          <div class="stat-label">总体完成率</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value">{{ summary.doneTasks }}</div>
          <div class="stat-label">已完成任务</div>
        </div>
        <div class="stat-tile">
          <div class="stat-value">{{ summary.totalTasks }}</div>
          <div class="stat-label">总任务数</div>
        </div>
      </div>

      <div class="progress-bar-track">
        <div
          class="progress-bar-inner"
          :style="{
            width: pct(summary.completionRate),
            background: barColor(summary.completionRate),
          }"
        />
      </div>

      <h3 class="h3-tight">按日明细</h3>
      <div v-if="!hasDaily" class="empty-hint inner-empty">
        <p>暂无历史计划记录。你可：</p>
        <p>
          <RouterLink to="/outline">去确认或选择大纲</RouterLink>
          →
          <RouterLink to="/plan">拉取今日计划</RouterLink>
          → 在任务上标记完成，再回到本页查看。
        </p>
        <p><RouterLink to="/">或从 AI 私教开始</RouterLink>，用自然语言走完整学习流。</p>
      </div>
      <div v-else class="view-table-wrap table-wrap">
        <table class="view-table">
          <thead>
            <tr>
              <th>日期 / 计划</th>
              <th class="cell-num">已完成</th>
              <th class="cell-num">总任务</th>
              <th>完成率</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(s, i) in summary.dailyStats" :key="i">
              <tr>
                <td>
                  <div class="plan-date-cell">
                    <button
                      v-if="s.tasks && s.tasks.length"
                      type="button"
                      class="exp-btn"
                      :id="`exp-btn-${i}`"
                      :aria-expanded="expanded === i"
                      :aria-controls="`exp-panel-${i}`"
                      @click="toggleRow(i)"
                    >
                      {{ expanded === i ? '▼' : '▶' }}
                    </button>
                    <div>
                      <div class="date-title">{{ s.planDate }}</div>
                      <div class="date-sub">{{ s.planTitle }}</div>
                    </div>
                  </div>
                </td>
                <td class="cell-num">{{ s.done }}</td>
                <td class="cell-num">{{ s.total }}</td>
                <td class="rate-cell">
                  <div class="rate-bar-row">
                    <div class="progress-bar-track progress-bar-track--sm">
                      <div
                        class="progress-bar-inner"
                        :style="{
                          width: pct(s.completionRate),
                          background: barColor(s.completionRate),
                        }"
                      />
                    </div>
                    <span class="rate-label">{{ pct(s.completionRate) }}</span>
                  </div>
                </td>
              </tr>
              <tr
                v-show="expanded === i"
                :id="`exp-panel-${i}`"
                class="exp-panel-row"
                role="region"
                :aria-labelledby="`exp-btn-${i}`"
              >
                <td colspan="4" class="detail-td">
                  <div v-if="!s.tasks?.length" class="sub-muted">暂无任务明细</div>
                  <div v-else class="task-detail">
                    <p class="sub-head">已完成</p>
                    <ul class="tlist done-list">
                      <li
                        v-for="(t, ti) in (s.tasks || []).filter((x) => x.done)"
                        :key="`d-${i}-${ti}`"
                      >
                        <span class="tstat done">✓</span> {{ t.description }}（{{ t.status }}）
                      </li>
                      <li v-if="!(s.tasks || []).filter((x) => x.done).length" class="sub-muted">无</li>
                    </ul>
                    <p class="sub-head sub-head--spaced">未完成</p>
                    <ul class="tlist todo-list">
                      <li
                        v-for="(t, ti) in (s.tasks || []).filter((x) => !x.done)"
                        :key="`t-${i}-${ti}`"
                      >
                        <span class="tstat todo">·</span> {{ t.description }}（{{ t.status }}）
                      </li>
                      <li v-if="!(s.tasks || []).filter((x) => !x.done).length" class="sub-muted">无</li>
                    </ul>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="card state-card empty-hint">
      暂无进度数据。请先
      <RouterLink to="/outline">保存一份大纲</RouterLink>
      与
      <RouterLink to="/plan">拉取计划</RouterLink>，
      并完成至少一项任务，或
      <RouterLink to="/">在私教中</RouterLink>推进学习流。
    </div>

    <div class="page-foot">
      <button type="button" class="secondary" @click="loadSummary">刷新</button>
    </div>
  </div>
  </LearningModuleShell>
</template>

<style scoped>
.inner-empty {
  color: var(--muted);
}
.inner-empty p {
  margin: 0.35rem 0;
}
.exp-btn {
  width: 1.6rem;
  min-height: 1.5rem;
  line-height: 1.1;
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  color: #8ab4f8;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.7rem;
  padding: 1px 4px 2px;
  flex-shrink: 0;
  margin-top: 2px;
}
.exp-btn:focus {
  outline: 2px solid #5b72e8;
  outline-offset: 1px;
}
.exp-panel-row[hidden] {
  display: none;
}
.sub-head {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--muted, #8899cc);
  margin: 0 0 0.3rem 0.25rem;
  text-transform: none;
  letter-spacing: 0.02em;
}
.sub-head--spaced {
  margin-top: 0.65rem;
}
.sub-muted {
  font-size: 0.85rem;
  color: var(--muted, #6b7a9e);
  margin: 0.1rem 0.25rem;
}
.task-detail {
  border-left: 2px solid #3b4db8;
  padding-left: 0.6rem;
  margin-left: 0.15rem;
}
.tlist {
  margin: 0;
  padding-left: 0.1rem;
  list-style: none;
  font-size: 0.88rem;
  line-height: 1.45;
}
.tlist li {
  margin-bottom: 0.35rem;
}
.tstat {
  display: inline-block;
  min-width: 0.8rem;
  color: #22c55e;
  font-size: 0.75rem;
  margin-right: 0.25rem;
  vertical-align: 0.05em;
}
.tstat.todo {
  color: #f59e0b;
}
.detail-td {
  padding: 0.5rem 0.5rem 0.9rem;
  background: var(--bg, #0f1419);
}
</style>
