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
  if (state === 'closed') return '正常（closed）'
  if (state === 'open') return '熔断开启（open）'
  return '半开探测（half_open）'
}

function cbClass(state: string) {
  if (state === 'closed') return 'badge badge-ok'
  if (state === 'open') return 'badge badge-err'
  return 'badge badge-warn'
}

function svcClass(v: string) {
  return v === 'ok' ? 'badge badge-ok' : 'badge badge-err'
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
  <div>
    <h1>可观测性监控</h1>
    <p class="lead">实时展示缓存命中率、Token 用量、熔断器状态等核心指标（每 30s 自动刷新）。</p>

    <div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
      <button type="button" :disabled="loading" @click="refresh">
        {{ loading ? '刷新中…' : '立即刷新' }}
      </button>
      <span v-if="lastUpdated" style="font-size:0.82rem;color:var(--muted)">最后更新：{{ lastUpdated }}</span>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- 健康状态 -->
    <div v-if="health" class="card">
      <h2>服务健康状态</h2>
      <div class="kv-row">
        <span class="kv-label">整体状态</span>
        <span :class="health.status === 'ok' ? 'badge badge-ok' : 'badge badge-warn'">{{ health.status }}</span>
      </div>
      <div v-for="(val, svc) in health.services" :key="svc" class="kv-row">
        <span class="kv-label">{{ svc }}</span>
        <span :class="svcClass(val)">{{ val }}</span>
      </div>
    </div>

    <!-- 熔断器 -->
    <div v-if="cb" class="card">
      <h2>LLM 熔断器状态</h2>
      <div class="kv-row">
        <span class="kv-label">当前状态</span>
        <span :class="cbClass(cb.state)">{{ cbLabel(cb.state) }}</span>
      </div>
      <div class="kv-row">
        <span class="kv-label">失败次数 / 阈值</span>
        <span>{{ cb.failure_count }} / {{ cb.failure_threshold }}</span>
      </div>
      <div class="kv-row">
        <span class="kv-label">冷却时长</span>
        <span>{{ cb.reset_timeout_seconds }}s</span>
      </div>
      <template v-if="cb.state === 'open'">
        <div class="kv-row">
          <span class="kv-label">已熔断时长</span>
          <span>{{ cb.open_for_seconds }}s</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">剩余冷却</span>
          <span>{{ cb.remaining_cooldown_seconds }}s</span>
        </div>
      </template>
    </div>

    <!-- 缓存命中率 -->
    <div v-if="stats && !stats.error" class="card">
      <h2>缓存命中率</h2>
      <div class="metric-grid">
        <div class="metric-item">
          <div class="metric-value">{{ pct(stats.cache.exact_hit_rate) }}%</div>
          <div class="metric-desc">精确命中率</div>
          <div class="metric-sub">命中 {{ stats.cache.exact_hit }} · 未中 {{ stats.cache.exact_miss }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ pct(stats.cache.semantic_hit_rate) }}%</div>
          <div class="metric-desc">语义命中率</div>
          <div class="metric-sub">命中 {{ stats.cache.semantic_hit }} · 未中 {{ stats.cache.semantic_miss }}</div>
        </div>
        <div class="metric-item accent">
          <div class="metric-value">{{ pct(stats.cache.combined_hit_rate) }}%</div>
          <div class="metric-desc">综合命中率</div>
          <div class="metric-sub">节省 LLM 调用比例</div>
        </div>
      </div>
      <!-- 进度条 -->
      <div style="margin-top:1rem">
        <div class="bar-label">精确缓存</div>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: pct(stats.cache.exact_hit_rate) + '%' }" />
        </div>
        <div class="bar-label" style="margin-top:0.5rem">语义缓存</div>
        <div class="bar-track">
          <div class="bar-fill bar-fill-sem" :style="{ width: pct(stats.cache.semantic_hit_rate) + '%' }" />
        </div>
      </div>
    </div>

    <!-- Token 用量 -->
    <div v-if="stats && !stats.error" class="card">
      <h2>Token 用量 &amp; 费用估算</h2>
      <div class="metric-grid">
        <div class="metric-item">
          <div class="metric-value">{{ stats.tokens.total_in.toLocaleString() }}</div>
          <div class="metric-desc">输入 Token（累计）</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ stats.tokens.total_out.toLocaleString() }}</div>
          <div class="metric-desc">输出 Token（累计）</div>
        </div>
        <div class="metric-item accent">
          <div class="metric-value">${{ stats.tokens.estimated_cost_usd }}</div>
          <div class="metric-desc">预估费用（USD）</div>
          <div class="metric-sub">DeepSeek 价格参考</div>
        </div>
      </div>
    </div>

    <!-- 请求统计 -->
    <div v-if="stats && !stats.error" class="card">
      <h2>请求统计</h2>
      <div class="metric-grid">
        <div class="metric-item">
          <div class="metric-value">{{ stats.requests.total }}</div>
          <div class="metric-desc">总请求数</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ stats.requests.error }}</div>
          <div class="metric-desc">错误请求数</div>
        </div>
        <div class="metric-item" :class="stats.requests.error_rate > 0.05 ? 'accent-err' : ''">
          <div class="metric-value">{{ pct(stats.requests.error_rate) }}%</div>
          <div class="metric-desc">错误率</div>
        </div>
        <div class="metric-item">
          <div class="metric-value">{{ stats.latency.avg_ms }} ms</div>
          <div class="metric-desc">平均延迟</div>
          <div class="metric-sub">采样 {{ stats.latency.sample_count }} 次</div>
        </div>
      </div>
    </div>

    <div v-if="stats?.error" class="card">
      <p class="error">指标不可用：{{ stats.error }}</p>
    </div>

    <!-- Session Token 查询 -->
    <div class="card">
      <h2>Session Token 配额查询</h2>
      <p class="lead" style="font-size:0.88rem">输入 Session ID 查看该用户在当前配额窗口内的 Token 消耗情况。</p>
      <div style="display:flex;gap:0.5rem;align-items:flex-end;flex-wrap:wrap">
        <div style="flex:1;min-width:180px">
          <label>Session ID</label>
          <input v-model="sessionIdInput" type="text" placeholder="例如：web-abc123" />
        </div>
        <button type="button" :disabled="sessionLoading || !sessionIdInput.trim()" @click="querySession">
          {{ sessionLoading ? '查询中…' : '查询' }}
        </button>
      </div>
      <p v-if="sessionError" class="error">{{ sessionError }}</p>

      <div v-if="sessionUsage" style="margin-top:1rem">
        <div class="kv-row">
          <span class="kv-label">已用 Token</span>
          <span>{{ sessionUsage.used_tokens.toLocaleString() }}</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">配额上限</span>
          <span>{{ sessionUsage.budget_enabled ? sessionUsage.budget.toLocaleString() : '无限制' }}</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">剩余配额</span>
          <span>{{ sessionUsage.remaining === -1 ? '无限制' : sessionUsage.remaining.toLocaleString() }}</span>
        </div>
        <div class="kv-row">
          <span class="kv-label">窗口剩余时间</span>
          <span>{{ sessionUsage.ttl_seconds }}s</span>
        </div>
        <div v-if="sessionUsage.budget_enabled" style="margin-top:0.75rem">
          <div class="bar-label">Token 配额使用率</div>
          <div class="bar-track">
            <div
              class="bar-fill"
              :class="sessionUsage.remaining < sessionUsage.budget * 0.1 ? 'bar-fill-err' : ''"
              :style="{ width: Math.min(100, (sessionUsage.used_tokens / sessionUsage.budget) * 100).toFixed(1) + '%' }"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kv-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--border);
}
.kv-row:last-child {
  border-bottom: none;
}
.kv-label {
  min-width: 130px;
  font-size: 0.85rem;
  color: var(--muted);
}

.badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-ok { background: rgba(34,197,94,0.15); color: #22c55e; }
.badge-err { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge-warn { background: rgba(234,179,8,0.15); color: #eab308; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.75rem;
  margin-top: 0.5rem;
}
.metric-item {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
}
.metric-item.accent {
  border-color: var(--accent);
}
.metric-item.accent-err {
  border-color: var(--danger);
}
.metric-value {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text);
}
.metric-desc {
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.2rem;
}
.metric-sub {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.1rem;
  opacity: 0.7;
}

.bar-label {
  font-size: 0.8rem;
  color: var(--muted);
  margin-bottom: 0.3rem;
}
.bar-track {
  height: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 5px;
  transition: width 0.4s ease;
}
.bar-fill-sem {
  background: #8b5cf6;
}
.bar-fill-err {
  background: var(--danger);
}
</style>
