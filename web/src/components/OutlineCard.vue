<script setup lang="ts">
import { ref } from 'vue'

interface Chapter {
  order: number
  title: string
  description: string
  estimated_hours: number
  key_concepts?: string[]
}

interface OutlinePayload {
  title: string
  goal: string
  estimated_days: number
  chapters: Chapter[]
}

const props = defineProps<{
  payload: OutlinePayload
  saving?: boolean
}>()

const emit = defineEmits<{
  confirm: []
}>()

const expanded = ref<number | null>(null)

function toggleChapter(idx: number) {
  expanded.value = expanded.value === idx ? null : idx
}
</script>

<template>
  <div class="outline-card">
    <div class="outline-card__header">
      <span class="outline-card__badge">📋 学习大纲</span>
      <h3 class="outline-card__title">{{ payload.title }}</h3>
      <p class="outline-card__meta">
        共 {{ payload.chapters.length }} 章节 · 预计 {{ payload.estimated_days }} 天
      </p>
    </div>

    <ol class="outline-card__chapters">
      <li
        v-for="(ch, idx) in payload.chapters"
        :key="ch.order"
        class="outline-card__chapter"
        :class="{ 'is-open': expanded === idx }"
        @click="toggleChapter(idx)"
      >
        <div class="outline-card__chapter-head">
          <span class="outline-card__chapter-num">{{ ch.order }}</span>
          <span class="outline-card__chapter-title">{{ ch.title }}</span>
          <span class="outline-card__chapter-hours">{{ ch.estimated_hours }}h</span>
          <span class="outline-card__caret">{{ expanded === idx ? '▲' : '▼' }}</span>
        </div>
        <div v-if="expanded === idx" class="outline-card__chapter-body">
          <p>{{ ch.description }}</p>
          <div v-if="ch.key_concepts?.length" class="outline-card__concepts">
            <span v-for="kc in ch.key_concepts" :key="kc" class="outline-card__concept-tag">
              {{ kc }}
            </span>
          </div>
        </div>
      </li>
    </ol>

    <button
      class="outline-card__btn"
      :disabled="saving"
      @click.stop="emit('confirm')"
    >
      <span v-if="saving">⏳ 保存中...</span>
      <span v-else>✅ 确认大纲，自动生成今日计划</span>
    </button>
  </div>
</template>

<style scoped>
.outline-card {
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  border-radius: 12px;
  padding: 1.25rem;
  margin: 0.5rem 0;
  width: 100%;
}
.outline-card__header {
  margin-bottom: 1rem;
}
.outline-card__badge {
  background: #3b4db8;
  color: #fff;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 600;
  display: inline-block;
  margin-bottom: 0.5rem;
}
.outline-card__title {
  margin: 0.25rem 0 0.25rem;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text, #e0e6f7);
}
.outline-card__meta {
  font-size: 0.82rem;
  color: var(--muted, #8899cc);
  margin: 0;
}
.outline-card__chapters {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.outline-card__chapter {
  background: var(--input-bg, #161924);
  border: 1px solid var(--border, #2e3450);
  border-radius: 8px;
  cursor: pointer;
  overflow: hidden;
  transition: border-color 0.2s;
}
.outline-card__chapter.is-open {
  border-color: #5b72e8;
}
.outline-card__chapter-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.9rem;
}
.outline-card__chapter-num {
  width: 22px;
  height: 22px;
  background: #3b4db8;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
}
.outline-card__chapter-title {
  flex: 1;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text, #e0e6f7);
}
.outline-card__chapter-hours {
  font-size: 0.78rem;
  color: var(--muted, #8899cc);
}
.outline-card__caret {
  font-size: 0.7rem;
  color: var(--muted, #8899cc);
}
.outline-card__chapter-body {
  padding: 0.5rem 0.9rem 0.75rem 2.8rem;
  font-size: 0.84rem;
  color: var(--muted, #8899cc);
  line-height: 1.5;
}
.outline-card__chapter-body p {
  margin: 0 0 0.4rem;
}
.outline-card__concepts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.outline-card__concept-tag {
  background: #2a3460;
  color: #8ab4f8;
  border-radius: 4px;
  padding: 1px 7px;
  font-size: 0.75rem;
}
.outline-card__btn {
  width: 100%;
  padding: 0.6rem;
  background: #3b4db8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.outline-card__btn:hover:not(:disabled) {
  background: #4a5fd4;
}
.outline-card__btn:disabled {
  background: #2a3460;
  color: #8899cc;
  cursor: not-allowed;
}
</style>
