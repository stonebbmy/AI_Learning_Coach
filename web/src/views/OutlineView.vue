<script setup lang="ts">
import { ref } from 'vue'
import {
  generateOutline,
  confirmOutline,
  toOutlineConfirmBody,
  updateTutorContext,
  type OutlineGenerateResponse,
} from '@/lib/api'
import { userStore } from '@/lib/userStore'

const target = ref('在 3 个月内从 Java 后端转向 AI 应用开发，掌握 LangChain、RAG 与 Agent 工程化')
const deadline = ref('3个月')

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const outline = ref<OutlineGenerateResponse | null>(null)
const savedId = ref<number | null>(userStore.state.currentOutlineId)

async function onGenerate() {
  error.value = ''
  outline.value = null
  savedId.value = null
  loading.value = true
  try {
    outline.value = await generateOutline(target.value.trim(), deadline.value.trim())
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function onConfirm() {
  if (!outline.value) return
  error.value = ''
  saving.value = true
  try {
    const res = (await confirmOutline(toOutlineConfirmBody(outline.value))) as { id?: number }
    const id = res.id ?? null
    savedId.value = id
    userStore.setOutlineId(id)
    // 同步大纲上下文到私教 Redis
    updateTutorContext({
      currentOutlineId: id,
      outlineChapters: outline.value?.chapters.map((c) => c.chapter_title) ?? [],
    }).catch(() => { /* 静默失败 */ })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <h1>学习大纲</h1>
    <p class="lead">调用 Python <code>/api/outline/generate</code>；确认后通过 Java <code>/api/outline/confirm</code> 落库。</p>

    <div class="card">
      <label>学习目标</label>
      <textarea v-model="target" rows="3" />

      <label style="margin-top: 0.75rem">期限</label>
      <input v-model="deadline" type="text" placeholder="例如：3个月" />

      <div style="margin-top: 1rem">
        <button type="button" :disabled="loading || !target.trim()" @click="onGenerate">
          {{ loading ? '生成中…' : '生成大纲' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="outline" class="card">
      <h2>{{ outline.title }}</h2>
      <p>{{ outline.overview }}</p>

      <div v-for="(ch, i) in outline.chapters" :key="i" class="chapter">
        <h3>{{ ch.chapter_title }}</h3>
        <p style="color: var(--muted); margin: 0; font-size: 0.95rem">{{ ch.description }}</p>
        <ul>
          <li v-for="(kp, j) in ch.key_points" :key="j">{{ kp }}</li>
        </ul>
      </div>

      <button type="button" class="secondary" :disabled="saving" @click="onConfirm">
        {{ saving ? '保存中…' : '确认并保存到数据库' }}
      </button>
      <p v-if="savedId !== null" style="margin-top: 0.75rem; color: var(--muted); font-size: 0.9rem">
        已保存，大纲 ID：{{ savedId }}（已关联到账户，生成计划时将自动带入章节）
      </p>
    </div>
  </div>
</template>
