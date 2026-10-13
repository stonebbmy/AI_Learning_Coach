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
    short: '忠实度',
    en: 'Faithfulness',
    desc: '答案是否完全来自检索上下文，无幻觉',
  },
  {
    key: 'answer_relevance' as const,
    short: '答案相关性',
    en: 'Answer Relevance',
    desc: '答案是否直接且完整地回答了问题',
  },
  {
    key: 'context_relevance' as const,
    short: '上下文相关性',
    en: 'Context Relevance',
    desc: '检索文档是否包含回答问题所需的关键信息',
  },
] as const
</script>

<template>
  <div class="dash">
    <header class="dash-hero">
      <div class="dash-hero__text">
        <p class="dash-eyebrow">RAG Evaluation</p>
        <h1>RAG 质量评估</h1>
        <p class="dash-lead">
          基于 <strong>LLM-as-Judge</strong> 三维打分。每次评估额外调用 3 次 LLM，请勿高频触发。
        </p>
      </div>
    </header>

    <section class="panel">
      <h2 class="panel-title">评估问题</h2>
      <div class="eval-compose">
        <textarea
          v-model="question"
          rows="3"
          class="eval-textarea"
          placeholder="输入一个问题，系统将自动执行 RAG 并评估结果…"
        />
        <div class="eval-compose__side">
          <button type="button" class="btn-primary" :disabled="loading || !question.trim()" @click="onEval">
            {{ loading ? '评估中…' : '开始评估' }}
          </button>
          <span v-if="loading" class="eval-hint">约 15–30 秒</span>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="loading" class="eval-loading">
        <div class="spinner" />
        <p>正在检索、生成并并发 Judge 评分…</p>
      </div>
    </section>

    <section v-if="result" class="panel panel--result">
      <h2 class="panel-title">评估结果</h2>

      <div class="score-board">
        <div class="score-ring" :style="{ '--score-color': scoreColor(result.scores.overall) }">
          <span class="score-ring__num">{{ Math.round(result.scores.overall * 100) }}</span>
          <span class="score-ring__cap">综合 / 100</span>
        </div>

        <div class="dim-cards">
          <article
            v-for="dim in DIMENSIONS"
            :key="dim.key"
            class="dim-card"
            :style="{ '--dim-color': scoreColor(result.scores[dim.key].score) }"
          >
            <div class="dim-card__head">
              <div>
                <h3 class="dim-card__title">{{ dim.short }}</h3>
                <p class="dim-card__en">{{ dim.en }}</p>
              </div>
              <span class="dim-card__badge">
                {{ scoreLabel(result.scores[dim.key].score) }}
                {{ (result.scores[dim.key].score * 100).toFixed(0) }}
              </span>
            </div>
            <p class="dim-card__desc">{{ dim.desc }}</p>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{
                  width: (result.scores[dim.key].score * 100).toFixed(1) + '%',
                  background: scoreColor(result.scores[dim.key].score),
                }"
              />
            </div>
            <p class="dim-card__reason">{{ result.scores[dim.key].reason }}</p>
          </article>
        </div>
      </div>

      <p class="interpretation" :style="{ borderColor: scoreColor(result.scores.overall) + '55' }">
        {{ result.interpretation }}
      </p>

      <div class="preview-row">
        <div class="preview-block">
          <h3 class="preview-block__title">RAG 回答</h3>
          <div class="preview-box">{{ result.answer_preview }}</div>
        </div>
        <div class="preview-block">
          <h3 class="preview-block__title">检索上下文</h3>
          <div class="preview-box preview-box--muted">{{ result.context_preview }}</div>
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
  padding: 1.25rem 1.35rem;
  border-radius: 14px;
  border: 1px solid rgba(139, 92, 246, 0.25);
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 50%, rgba(88, 28, 135, 0.1) 100%);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.28);
}
.dash-eyebrow {
  margin: 0 0 0.2rem;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #c4b5fd;
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
  max-width: 40rem;
}
.dash-lead strong {
  color: #e2e8f0;
  font-weight: 600;
}

.panel {
  padding: 1.15rem 1.25rem;
  border-radius: 12px;
  border: 1px solid rgba(45, 58, 77, 0.9);
  background: linear-gradient(160deg, rgba(26, 35, 50, 0.92) 0%, rgba(18, 24, 35, 0.98) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.panel-title {
  margin: 0 0 0.85rem;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #a8b8d0;
}

.eval-compose {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
@media (min-width: 768px) {
  .eval-compose {
    flex-direction: row;
    align-items: stretch;
  }
}
.eval-textarea {
  flex: 1;
  min-width: 0;
  min-height: 5.5rem;
  resize: vertical;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(8, 12, 20, 0.55);
  color: var(--text);
  font-size: 0.92rem;
  line-height: 1.5;
}
.eval-compose__side {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: stretch;
  gap: 0.35rem;
  min-width: 7.5rem;
}
.eval-hint {
  font-size: 0.75rem;
  color: var(--muted);
  text-align: center;
}

.btn-primary {
  padding: 0.55rem 1rem;
  border-radius: 8px;
  border: none;
  background: linear-gradient(180deg, #4f6ef7 0%, #3b4db8 100%);
  color: #fff;
  font-weight: 600;
  font-size: 0.88rem;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 77, 184, 0.45);
}
.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.eval-loading {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(45, 58, 77, 0.7);
  color: var(--muted);
  font-size: 0.88rem;
}
.eval-loading p {
  margin: 0;
}

.score-board {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: stretch;
}
@media (min-width: 960px) {
  .score-board {
    grid-template-columns: 11rem minmax(0, 1fr);
  }
}

.score-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.25rem 1rem;
  border-radius: 12px;
  border: 2px solid var(--score-color, #3b82f6);
  background: radial-gradient(circle at 50% 30%, color-mix(in srgb, var(--score-color) 18%, transparent), rgba(8, 12, 20, 0.5));
  min-height: 8.5rem;
}
.score-ring__num {
  font-size: 2.75rem;
  font-weight: 800;
  line-height: 1;
  color: var(--score-color);
  font-variant-numeric: tabular-nums;
}
.score-ring__cap {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--muted);
}

.dim-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.65rem;
}
@media (min-width: 720px) {
  .dim-cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.dim-card {
  padding: 0.85rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(45, 58, 77, 0.75);
  background: rgba(8, 12, 20, 0.45);
  border-top: 2px solid var(--dim-color);
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.dim-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.dim-card__title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
}
.dim-card__en {
  margin: 0.1rem 0 0;
  font-size: 0.68rem;
  color: var(--muted);
  letter-spacing: 0.02em;
}
.dim-card__badge {
  flex-shrink: 0;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  background: color-mix(in srgb, var(--dim-color) 20%, transparent);
  color: var(--dim-color);
}
.dim-card__desc {
  margin: 0 0 0.45rem;
  font-size: 0.75rem;
  color: var(--muted);
  line-height: 1.4;
}
.dim-card__reason {
  margin: 0.45rem 0 0;
  font-size: 0.78rem;
  color: #94a3b8;
  line-height: 1.45;
  flex: 1;
}

.bar-track {
  height: 6px;
  background: rgba(8, 12, 20, 0.8);
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
}

.interpretation {
  margin: 1rem 0 0;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border-left: 3px solid;
  background: rgba(8, 12, 20, 0.45);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
}

.preview-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(45, 58, 77, 0.7);
}
@media (min-width: 768px) {
  .preview-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.preview-block__title {
  margin: 0 0 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #a8b8d0;
}
.preview-box {
  white-space: pre-wrap;
  word-break: break-word;
  padding: 0.75rem 0.85rem;
  border-radius: 10px;
  border: 1px solid rgba(45, 58, 77, 0.65);
  background: rgba(8, 12, 20, 0.55);
  font-size: 0.88rem;
  line-height: 1.55;
  max-height: min(260px, 38vh);
  overflow-y: auto;
}
.preview-box--muted {
  font-size: 0.82rem;
  color: #94a3b8;
}

.spinner {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: 2px solid rgba(45, 58, 77, 0.8);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
