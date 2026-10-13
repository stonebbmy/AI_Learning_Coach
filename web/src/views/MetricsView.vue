<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  fetchMetricsStats,
  fetchCircuitBreaker,
  fetchHealthDetail,
  fetchSessionTokenUsage,
  type MetricsStats,
  type CircuitBreakerStatus,
  type HealthDetail,
  type SessionTokenUsage,
} from '@/lib/api'

const stats = ref<MetricsStats | null>(null)
const cb = ref<CircuitBreakerStatus | null>(null)
const health = ref<HealthDetail | null>(null)
const loading = ref(false)
const error = ref('')
const lastUpdated = ref('')

const sessionIdInput = ref('')
const sessionUsage = ref<SessionTokenUsage | null>(null)
const sessionLoading = ref(false)
const sessionError = ref('')

let timer: ReturnType<typeof setInterval> | null = null

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [s, c, h] = await Promise.all([
      fetchMetricsStats(),
      fetchCircuitBreaker(),
      fetchHealthDetail(),
    ])
    stats.value = s
    cb.value = c
    health.value = h
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function querySession() {
  const sid = sessionIdInput.value.trim()
  if (!sid) return
  sessionLoading.value = true
  sessionError.value = ''
  sessionUsage.value = null
  try {
    sessionUsage.value = await fetchSessionTokenUsage(sid)
    if (sessionUsage.value.error) {
      sessionError.value = sessionUsage.value.error
      sessionUsage.value = null
    }
  } catch (e) {
    sessionError.value = e instanceof Error ? e.message : String(e)
  } finally {
    sessionLoading.value = false
  }
}

function pct(v: number) {
  return (v * 100).toFixed(1)
}

function cbLabel(state: string) {
  if (state === 'closed') return '正常'
  if (state === 'open') return '熔断中'
  return '半开探测'
}

function cbClass(state: string) {
  if (state === 'closed') return 'chip chip--ok'
  if (state === 'open') return 'chip chip--err'
  return 'chip chip--warn'
}

function svcClass(v: string) {
  return v === 'ok' ? 'chip chip--ok' : 'chip chip--err'
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 30_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="dash">
    <header class="dash-hero">
      <div class="dash-hero__text">
        <p class="dash-eyebrow">Observability</p>
        <h1>可观测性监控</h1>
        <p class="dash-lead">缓存、Token、熔断与健康状态 · 每 30 秒自动刷新</p>
      </div>
      <div class="dash-hero__actions">
        <button type="button" class="btn-primary" :disabled="loading" @click="refresh">
          {{ loading ? '刷新中…' : '立即刷新' }}
        </button>
        <span v-if="lastUpdated" class="dash-muted">更新于 {{ lastUpdated }}</span>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- 系统状态条 -->
    <section v-if="health || cb" class="panel panel--compact">
      <h2 class="panel-title">系统状态</h2>
      <div class="status-flow">
        <template v-if="health">
          <div class="status-item">
            <span class="status-item__label">整体</span>
            <span :class="health.status === 'ok' ? 'chip chip--ok' : 'chip chip--warn'">{{ health.status }}</span>
          </div>
          <div v-for="(val, svc) in health.services" :key="String(svc)" class="status-item">
            <span class="status-item__label">{{ svc }}</span>
            <span :class="svcClass(val)">{{ val }}</span>
          </div>
        </template>
        <span v-if="health && cb" class="status-divider" aria-hidden="true" />
        <template v-if="cb">
          <div class="status-item">
            <span class="status-item__label">LLM 熔断</span>
            <span :class="cbClass(cb.state)">{{ cbLabel(cb.state) }}</span>
          </div>
          <div class="status-item">
            <span class="status-item__label">失败 / 阈值</span>
            <span class="status-item__val">{{ cb.failure_count }} / {{ cb.failure_threshold }}</span>
          </div>
          <div class="status-item">
            <span class="status-item__label">冷却</span>
            <span class="status-item__val">{{ cb.reset_timeout_seconds }}s</span>
          </div>
          <template v-if="cb.state === 'open'">
            <div class="status-item">
              <span class="status-item__label">已熔断</span>
              <span class="status-item__val">{{ cb.open_for_seconds }}s</span>
            </div>
            <div class="status-item">
              <span class="status-item__label">剩余冷却</span>
              <span class="status-item__val">{{ cb.remaining_cooldown_seconds }}s</span>
            </div>
          </template>
        </template>
      </div>
    </section>

    <template v-if="stats && !stats.error">
      <!-- 核心 KPI -->
      <section class="kpi-strip">
        <div class="kpi kpi--highlight">
          <span class="kpi__label">综合缓存命中</span>
          <span class="kpi__value">{{ pct(stats.cache.combined_hit_rate) }}<small>%</small></span>
        </div>
        <div class="kpi">
          <span class="kpi__label">总请求</span>
          <span class="kpi__value">{{ stats.requests.total }}</span>
        </div>
        <div class="kpi">
          <span class="kpi__label">平均延迟</span>
          <span class="kpi__value">{{ stats.latency.avg_ms }}<small>ms</small></span>
        </div>
        <div class="kpi">
          <span class="kpi__label">预估费用</span>
          <span class="kpi__value kpi__value--money">${{ stats.tokens.estimated_cost_usd }}</span>
        </div>
      </section>

      <div class="dash-columns">
        <!-- 缓存 -->
        <section class="panel">
          <h2 class="panel-title">缓存命中率</h2>
          <div class="stat-grid stat-grid--3">
            <div class="stat-tile">
              <span class="stat-tile__val">{{ pct(stats.cache.exact_hit_rate) }}%</span>
              <span class="stat-tile__name">精确命中</span>
              <span class="stat-tile__sub">命中 {{ stats.cache.exact_hit }} · 未中 {{ stats.cache.exact_miss }}</span>
            </div>
            <div class="stat-tile">
              <span class="stat-tile__val">{{ pct(stats.cache.semantic_hit_rate) }}%</span>
              <span class="stat-tile__name">语义命中</span>
              <span class="stat-tile__sub">命中 {{ stats.cache.semantic_hit }} · 未中 {{ stats.cache.semantic_miss }}</span>
            </div>
            <div class="stat-tile stat-tile--accent">
              <span class="stat-tile__val">{{ pct(stats.cache.combined_hit_rate) }}%</span>
              <span class="stat-tile__name">综合命中</span>
              <span class="stat-tile__sub">节省 LLM 调用</span>
            </div>
          </div>
          <div class="bar-group">
            <div class="bar-row">
              <span class="bar-row__label">精确缓存</span>
              <div class="bar-track">
                <div class="bar-fill bar-fill--blue" :style="{ width: pct(stats.cache.exact_hit_rate) + '%' }" />
              </div>
              <span class="bar-row__pct">{{ pct(stats.cache.exact_hit_rate) }}%</span>
            </div>
            <div class="bar-row">
              <span class="bar-row__label">语义缓存</span>
              <div class="bar-track">
                <div class="bar-fill bar-fill--violet" :style="{ width: pct(stats.cache.semantic_hit_rate) + '%' }" />
              </div>
              <span class="bar-row__pct">{{ pct(stats.cache.semantic_hit_rate) }}%</span>
            </div>
          </div>
        </section>

        <!-- 用量与请求 -->
        <section class="panel">
          <h2 class="panel-title">Token 用量与请求</h2>
          <div class="stat-grid stat-grid--2">
            <div class="stat-tile">
              <span class="stat-tile__val">{{ stats.tokens.total_in.toLocaleString() }}</span>
              <span class="stat-tile__name">输入 Token</span>
            </div>
            <div class="stat-tile">
              <span class="stat-tile__val">{{ stats.tokens.total_out.toLocaleString() }}</span>
              <span class="stat-tile__name">输出 Token</span>
            </div>
            <div class="stat-tile">
              <span class="stat-tile__val">{{ stats.requests.error }}</span>
              <span class="stat-tile__name">错误请求</span>
            </div>
            <div class="stat-tile" :class="{ 'stat-tile--warn': stats.requests.error_rate > 0.05 }">
              <span class="stat-tile__val">{{ pct(stats.requests.error_rate) }}%</span>
              <span class="stat-tile__name">错误率</span>
            </div>
          </div>
          <p class="panel-footnote">
            延迟采样 {{ stats.latency.sample_count }} 次 · 费用按 DeepSeek 参考价估算
          </p>
        </section>
      </div>
    </template>

    <section v-if="stats?.error" class="panel">
      <p class="error">指标不可用：{{ stats.error }}</p>
    </section>

    <!-- Session -->
    <section class="panel panel--session">
      <h2 class="panel-title">Session Token 配额</h2>
      <p class="dash-muted panel-desc">查询指定 Session 在当前窗口内的 Token 消耗与剩余配额。</p>
      <div class="session-bar">
        <input
          v-model="sessionIdInput"
          type="text"
          class="session-input"
          placeholder="Session ID，例如 web-abc123"
        />
        <button type="button" class="btn-primary" :disabled="sessionLoading || !sessionIdInput.trim()" @click="querySession">
          {{ sessionLoading ? '查询中…' : '查询' }}
        </button>
      </div>
      <p v-if="sessionError" class="error">{{ sessionError }}</p>

      <div v-if="sessionUsage" class="session-result">
        <div class="session-stats">
          <div class="session-stat">
            <span class="session-stat__label">已用</span>
            <span class="session-stat__val">{{ sessionUsage.used_tokens.toLocaleString() }}</span>
          </div>
          <div class="session-stat">
            <span class="session-stat__label">上限</span>
            <span class="session-stat__val">{{ sessionUsage.budget_enabled ? sessionUsage.budget.toLocaleString() : '∞' }}</span>
          </div>
          <div class="session-stat">
            <span class="session-stat__label">剩余</span>
            <span class="session-stat__val">{{ sessionUsage.remaining === -1 ? '∞' : sessionUsage.remaining.toLocaleString() }}</span>
          </div>
          <div class="session-stat">
            <span class="session-stat__label">窗口 TTL</span>
            <span class="session-stat__val">{{ sessionUsage.ttl_seconds }}s</span>
          </div>
        </div>
        <div v-if="sessionUsage.budget_enabled" class="bar-row bar-row--wide">
          <span class="bar-row__label">配额使用</span>
          <div class="bar-track">
            <div
              class="bar-fill"
              :class="sessionUsage.remaining < sessionUsage.budget * 0.1 ? 'bar-fill--err' : 'bar-fill--blue'"
              :style="{ width: Math.min(100, (sessionUsage.used_tokens / sessionUsage.budget) * 100).toFixed(1) + '%' }"
            />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dash {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.dash-hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.35rem;
  border-radius: 14px;
  border: 1px solid rgba(59, 130, 246, 0.22);
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 55%, rgba(30, 58, 138, 0.12) 100%);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.28);
}
.dash-eyebrow {
  margin: 0 0 0.2rem;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #93c5fd;
}
.dash-hero h1 {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.dash-lead {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: var(--muted);
  max-width: 36rem;
}
.dash-hero__actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.4rem;
}
.dash-muted {
  font-size: 0.8rem;
  color: var(--muted);
}

.btn-primary {
  padding: 0.45rem 1.1rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(180deg, #4f6ef7 0%, #3b4db8 100%);
  color: #fff;
  font-weight: 600;
  font-size: 0.88rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(59, 77, 184, 0.45);
}
.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.panel {
  padding: 1.15rem 1.25rem;
  border-radius: 12px;
  border: 1px solid rgba(45, 58, 77, 0.9);
  background: linear-gradient(160deg, rgba(26, 35, 50, 0.92) 0%, rgba(18, 24, 35, 0.98) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.panel--compact {
  padding: 1rem 1.25rem;
}
.panel-title {
  margin: 0 0 0.85rem;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #a8b8d0;
}
.panel-desc {
  margin: -0.35rem 0 0.85rem;
}
.panel-footnote {
  margin: 0.85rem 0 0;
  font-size: 0.78rem;
  color: var(--muted);
}

.status-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem 1.1rem;
}
.status-divider {
  width: 1px;
  height: 1.75rem;
  background: rgba(139, 156, 179, 0.35);
  margin: 0 0.25rem;
}
.status-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.status-item__label {
  font-size: 0.8rem;
  color: var(--muted);
}
.status-item__val {
  font-size: 0.88rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.chip {
  display: inline-block;
  padding: 0.12rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.chip--ok {
  background: rgba(34, 197, 94, 0.18);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.35);
}
.chip--err {
  background: rgba(239, 68, 68, 0.18);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.35);
}
.chip--warn {
  background: rgba(234, 179, 8, 0.18);
  color: #facc15;
  border: 1px solid rgba(234, 179, 8, 0.35);
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
@media (min-width: 768px) {
  .kpi-strip {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.kpi {
  padding: 1rem 1.1rem;
  border-radius: 12px;
  border: 1px solid rgba(45, 58, 77, 0.85);
  background: rgba(15, 20, 30, 0.65);
}
.kpi--highlight {
  border-color: rgba(59, 130, 246, 0.45);
  background: linear-gradient(145deg, rgba(37, 99, 235, 0.12) 0%, rgba(15, 20, 30, 0.8) 100%);
}
.kpi__label {
  display: block;
  font-size: 0.78rem;
  color: var(--muted);
  margin-bottom: 0.35rem;
}
.kpi__value {
  font-size: 1.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.kpi__value small {
  font-size: 0.55em;
  font-weight: 600;
  margin-left: 0.1em;
  opacity: 0.85;
}
.kpi__value--money {
  font-size: 1.45rem;
}

.dash-columns {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: stretch;
}
@media (min-width: 900px) {
  .dash-columns {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.stat-grid {
  display: grid;
  gap: 0.65rem;
}
.stat-grid--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.stat-grid--2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
@media (max-width: 640px) {
  .stat-grid--3 {
    grid-template-columns: 1fr;
  }
}

.stat-tile {
  padding: 0.75rem 0.85rem;
  border-radius: 10px;
  border: 1px solid rgba(45, 58, 77, 0.7);
  background: rgba(8, 12, 20, 0.45);
  min-height: 5.5rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.stat-tile--accent {
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(37, 99, 235, 0.08);
}
.stat-tile--warn {
  border-color: rgba(239, 68, 68, 0.45);
}
.stat-tile__val {
  font-size: 1.35rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.stat-tile__name {
  font-size: 0.78rem;
  color: var(--muted);
  margin-top: 0.15rem;
}
.stat-tile__sub {
  font-size: 0.7rem;
  color: var(--muted);
  opacity: 0.85;
  margin-top: 0.2rem;
}

.bar-group {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.bar-row {
  display: grid;
  grid-template-columns: 4.5rem 1fr 2.75rem;
  align-items: center;
  gap: 0.5rem;
}
.bar-row--wide {
  grid-template-columns: 4.5rem 1fr;
  margin-top: 0.75rem;
}
.bar-row__label {
  font-size: 0.78rem;
  color: var(--muted);
}
.bar-row__pct {
  font-size: 0.78rem;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #93c5fd;
}
.bar-track {
  height: 8px;
  background: rgba(8, 12, 20, 0.8);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(45, 58, 77, 0.6);
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
}
.bar-fill--blue {
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
}
.bar-fill--violet {
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
}
.bar-fill--err {
  background: linear-gradient(90deg, #dc2626, #f87171);
}

.session-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: stretch;
}
.session-input {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(8, 12, 20, 0.6);
  color: var(--text);
  font-size: 0.9rem;
}
.session-result {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(45, 58, 77, 0.7);
}
.session-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}
@media (min-width: 720px) {
  .session-stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.session-stat {
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  background: rgba(8, 12, 20, 0.45);
  border: 1px solid rgba(45, 58, 77, 0.55);
}
.session-stat__label {
  display: block;
  font-size: 0.72rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.session-stat__val {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 0.2rem;
  font-variant-numeric: tabular-nums;
}
</style>
