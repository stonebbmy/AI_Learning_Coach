<script setup lang="ts">
import { ref } from 'vue'
import { evalRag, type RagEvalResponse } from '@/lib/api'

const question = ref('RAG 检索增强生成的核心流程是什么？')
const loading = ref(false)
const error = ref('')
const result = ref<RagEvalResponse | null>(null)

async function onEval() {
  const q = question.value.trim()
  if (!q) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await evalRag(q)
    if (result.value.error) {
      error.value = result.value.error
      result.value = null
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function scoreColor(score: number) {
  if (score >= 0.8) return '#22c55e'
  if (score >= 0.6) return '#eab308'
  if (score >= 0.4) return '#f97316'
  return '#ef4444'
}

function scoreLabel(score: number) {
  if (score >= 0.8) return '优秀'
  if (score >= 0.6) return '良好'
  if (score >= 0.4) return '一般'
  return '较差'
}

const DIMENSIONS = [
  {
    key: 'faithfulness' as const,
    label: '忠实度（Faithfulness）',
    desc: '答案是否完全来自检索上下文，无幻觉',
  },
  {
    key: 'answer_relevance' as const,
    label: '答案相关性（Answer Relevance）',
    desc: '答案是否直接且完整地回答了问题',
  },
  {
    key: 'context_relevance' as const,
    label: '上下文相关性（Context Relevance）',
    desc: '检索到的文档是否包含回答问题所需的关键信息',
  },
] as const
</script>

<template>
  <div>
    <h1>RAG 质量评估</h1>
    <p class="lead">
      基于 <strong>LLM-as-Judge</strong> 对 RAG 回答进行三维评分：忠实度、答案相关性、上下文相关性。
      每次评估会额外调用 3 次 LLM，请勿高频触发。
    </p>

    <div class="card">
      <label>评估问题</label>
      <textarea v-model="question" rows="3" placeholder="输入一个问题，系统将自动执行 RAG 并评估结果…" />
      <div style="margin-top:1rem">
        <button type="button" :disabled="loading || !question.trim()" @click="onEval">
          {{ loading ? '评估中（需约 15-30s）…' : '开始评估' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="loading" class="card" style="text-align:center;padding:2rem">
      <div class="spinner" />
      <p style="color:var(--muted);margin-top:1rem;font-size:0.9rem">
        正在执行 RAG 检索 + 生成，并并发调用 LLM Judge 评分，请稍候…
      </p>
    </div>

    <template v-if="result">
      <!-- 综合评分 -->
      <div class="card overall-card">
        <div class="overall-score" :style="{ color: scoreColor(result.scores.overall) }">
          {{ Math.round(result.scores.overall * 100) }}
        </div>
        <div class="overall-label">综合评分（满分 100）</div>
        <div class="interpretation">{{ result.interpretation }}</div>
      </div>

      <!-- 三维评分 -->
      <div class="card">
        <h2>评分详情</h2>
        <div v-for="dim in DIMENSIONS" :key="dim.key" class="dim-row">
          <div class="dim-header">
            <span class="dim-name">{{ dim.label }}</span>
            <span class="dim-badge" :style="{ background: scoreColor(result.scores[dim.key].score) + '22', color: scoreColor(result.scores[dim.key].score) }">
              {{ scoreLabel(result.scores[dim.key].score) }}
              {{ (result.scores[dim.key].score * 100).toFixed(0) }}分
            </span>
          </div>
          <p class="dim-desc">{{ dim.desc }}</p>
          <div class="bar-track">
            <div
              class="bar-fill"
              :style="{
                width: (result.scores[dim.key].score * 100).toFixed(1) + '%',
                background: scoreColor(result.scores[dim.key].score),
              }"
            />
          </div>
          <p class="dim-reason">{{ result.scores[dim.key].reason }}</p>
        </div>
      </div>

      <!-- RAG 输出预览 -->
      <div class="card">
        <h2>RAG 回答预览</h2>
        <div class="preview-box">{{ result.answer_preview }}</div>
      </div>

      <div class="card">
        <h2>检索上下文预览</h2>
        <div class="preview-box context-box">{{ result.context_preview }}</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.overall-card {
  text-align: center;
  padding: 2rem 1.25rem;
}
.overall-score {
  font-size: 4rem;
  font-weight: 800;
  line-height: 1;
}
.overall-label {
  font-size: 0.9rem;
  color: var(--muted);
  margin-top: 0.4rem;
}
.interpretation {
  margin-top: 0.75rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
}

.dim-row {
  padding: 0.9rem 0;
  border-bottom: 1px solid var(--border);
}
.dim-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.dim-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.3rem;
}
.dim-name {
  font-weight: 600;
  font-size: 0.95rem;
}
.dim-badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 600;
}
.dim-desc {
  font-size: 0.82rem;
  color: var(--muted);
  margin: 0 0 0.5rem;
}
.dim-reason {
  font-size: 0.85rem;
  color: var(--muted);
  margin: 0.5rem 0 0;
  font-style: italic;
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
  border-radius: 5px;
  transition: width 0.4s ease;
}

.preview-box {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 0.75rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.9rem;
  max-height: 220px;
  overflow-y: auto;
}
.context-box {
  font-size: 0.82rem;
  color: var(--muted);
}

/* 加载动画 */
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
