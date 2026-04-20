<script setup lang="ts">
import { ref } from 'vue'
import { uploadKnowledge } from '@/lib/api'

const file = ref<File | null>(null)
const loading = ref(false)
const message = ref('')
const error = ref('')

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function onUpload() {
  if (!file.value) return
  error.value = ''
  message.value = ''
  loading.value = true
  try {
    const res = await uploadKnowledge(file.value)
    message.value = res.message || (res.success ? '上传成功' : '完成')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <h1>知识库上传</h1>
    <p class="lead">调用 Python <code>POST /api/knowledge/upload</code>，仅支持 <code>.md</code> 文件。</p>

    <div class="card">
      <label>选择 Markdown 文件</label>
      <input type="file" accept=".md" @change="onFile" />

      <div style="margin-top: 1rem">
        <button type="button" :disabled="loading || !file" @click="onUpload">
          {{ loading ? '上传中…' : '上传到向量库' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message" style="margin-top: 0.5rem; color: var(--muted)">{{ message }}</p>
    </div>
  </div>
</template>
