<script setup lang="ts">
import { ref } from 'vue'

interface QuizQuestion {
  question: string
  type: 'choice' | 'open'
  options?: string[]
  answer: string
  explanation?: string
}

defineProps<{
  questions: QuizQuestion[]
}>()

const answers = ref<Record<number, string>>({})
const revealed = ref<Record<number, boolean>>({})
const score = ref<number | null>(null)

function selectOption(idx: number, option: string) {
  if (revealed.value[idx]) return
  answers.value[idx] = option
}

function reveal(idx: number) {
  revealed.value[idx] = true
}

function submitAll(questions: QuizQuestion[]) {
  let correct = 0
  questions.forEach((q, idx) => {
    if (!q.options) return // open 题不计分
    if ((answers.value[idx] || '').trim() === q.answer.trim()) correct++
  })
  const choiceCount = questions.filter((q) => q.type === 'choice').length
  score.value = choiceCount > 0 ? Math.round((correct / choiceCount) * 100) : 0
  Object.keys(answers.value).forEach((k) => {
    revealed.value[Number(k)] = true
  })
}
</script>

<template>
  <div class="quiz-card">
    <div class="quiz-card__header">
      <span class="quiz-card__badge">📝 课后测验</span>
      <span class="quiz-card__count">共 {{ questions.length }} 题</span>
    </div>

    <div v-for="(q, idx) in questions" :key="idx" class="quiz-card__question">
      <p class="quiz-card__q-text"><b>{{ idx + 1 }}.</b> {{ q.question }}</p>

      <!-- 选择题 -->
      <div v-if="q.type === 'choice' && q.options" class="quiz-card__options">
        <button
          v-for="opt in q.options"
          :key="opt"
          class="quiz-card__option"
          :class="{
            'is-selected': answers[idx] === opt && !revealed[idx],
            'is-correct': revealed[idx] && opt === q.answer,
            'is-wrong': revealed[idx] && answers[idx] === opt && opt !== q.answer,
          }"
          @click="selectOption(idx, opt)"
        >
          {{ opt }}
        </button>
      </div>

      <!-- 简答题 -->
      <textarea
        v-if="q.type === 'open'"
        v-model="answers[idx]"
        class="quiz-card__textarea"
        placeholder="请输入你的答案..."
        :disabled="revealed[idx]"
      />

      <div class="quiz-card__actions">
        <button
          v-if="!revealed[idx]"
          class="quiz-card__reveal-btn"
          :disabled="!answers[idx]"
          @click="reveal(idx)"
        >
          查看答案
        </button>
        <div v-else class="quiz-card__explanation">
          <span class="quiz-card__answer-label">正确答案：</span>{{ q.answer }}
          <p v-if="q.explanation" class="quiz-card__exp-text">{{ q.explanation }}</p>
        </div>
      </div>
    </div>

    <div v-if="score !== null" class="quiz-card__score">
      选择题得分：{{ score }}%
      <span v-if="score >= 80">🎉 很棒！</span>
      <span v-else-if="score >= 60">👍 继续加油！</span>
      <span v-else>💪 再复习一下！</span>
    </div>

    <button
      v-if="score === null"
      class="quiz-card__submit-btn"
      @click="submitAll(questions)"
    >
      提交答案
    </button>
  </div>
</template>

<style scoped>
.quiz-card {
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  border-radius: 12px;
  padding: 1.25rem;
  margin: 0.5rem 0;
  width: 100%;
}
.quiz-card__header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.quiz-card__badge {
  background: #2a6049;
  color: #6ee7b7;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 600;
}
.quiz-card__count {
  font-size: 0.82rem;
  color: var(--muted, #8899cc);
}
.quiz-card__question {
  margin-bottom: 1.25rem;
}
.quiz-card__q-text {
  font-size: 0.92rem;
  color: var(--text, #e0e6f7);
  margin: 0 0 0.5rem;
  line-height: 1.5;
}
.quiz-card__options {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.quiz-card__option {
  text-align: left;
  padding: 0.45rem 0.75rem;
  background: var(--input-bg, #161924);
  border: 1px solid var(--border, #2e3450);
  border-radius: 6px;
  color: var(--text, #e0e6f7);
  font-size: 0.85rem;
  cursor: pointer;
  transition: border-color 0.15s;
}
.quiz-card__option:hover {
  border-color: #5b72e8;
}
.quiz-card__option.is-selected {
  border-color: #5b72e8;
  background: #1e2a4a;
}
.quiz-card__option.is-correct {
  border-color: #22c55e;
  background: #0f2a1e;
  color: #6ee7b7;
}
.quiz-card__option.is-wrong {
  border-color: #ef4444;
  background: #2a1020;
  color: #fca5a5;
}
.quiz-card__textarea {
  width: 100%;
  min-height: 80px;
  padding: 0.5rem;
  background: var(--input-bg, #161924);
  border: 1px solid var(--border, #2e3450);
  border-radius: 6px;
  color: var(--text, #e0e6f7);
  font-size: 0.85rem;
  resize: vertical;
  box-sizing: border-box;
}
.quiz-card__actions {
  margin-top: 0.5rem;
}
.quiz-card__reveal-btn {
  padding: 0.3rem 0.8rem;
  background: transparent;
  border: 1px solid #5b72e8;
  border-radius: 6px;
  color: #8ab4f8;
  font-size: 0.82rem;
  cursor: pointer;
}
.quiz-card__reveal-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.quiz-card__explanation {
  font-size: 0.83rem;
  color: #6ee7b7;
  line-height: 1.4;
}
.quiz-card__answer-label {
  font-weight: 600;
  margin-right: 0.25rem;
}
.quiz-card__exp-text {
  color: var(--muted, #8899cc);
  margin: 0.25rem 0 0;
}
.quiz-card__score {
  text-align: center;
  font-size: 1.1rem;
  font-weight: 700;
  color: #6ee7b7;
  margin: 0.5rem 0;
  padding: 0.75rem;
  background: #0f2a1e;
  border-radius: 8px;
}
.quiz-card__submit-btn {
  width: 100%;
  padding: 0.6rem;
  background: #2a6049;
  color: #6ee7b7;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}
.quiz-card__submit-btn:hover {
  background: #3a8060;
}
</style>
