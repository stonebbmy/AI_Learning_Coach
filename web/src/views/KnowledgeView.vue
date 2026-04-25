<script setup lang="ts">
import { ref, onMounted } from 'vue'
import LearningModuleShell from '@/components/LearningModuleShell.vue'
import {
  uploadKnowledge,
  fetchKnowledgeSummary,
  fetchKnowledgeChunks,
  type KnowledgeSummaryResponse,
  type KnowledgeChunkItem,
} from '@/lib/api'

const file = ref<File | null>(null)
const uploadLoading = ref(false)
const message = ref('')
const error = ref('')

const summary = ref<KnowledgeSummaryResponse | null>(null)
const summaryLoading = ref(false)
const summaryError = ref('')

const selectedSource = ref<string | null>(null)
const viewAll = ref(false)
const chunks = ref<KnowledgeChunkItem[]>([])
const chunkOffset = ref(0)
const chunksLoading = ref(false)
const chunksError = ref('')
const chunksHasMore = ref(false)
const pageSize = 20

const filterLabel = ref('')

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function loadSummary() {
  summaryError.value = ''
  summaryLoading.value = true
  try {
    summary.value = await fetchKnowledgeSummary()
  } catch (e) {
    summaryError.value = e instanceof Error ? e.message : String(e)
    summary.value = null
  } finally {
    summaryLoading.value = false
  }
}

async function onUpload() {
  if (!file.value) return
  error.value = ''
  message.value = ''
  uploadLoading.value = true
  try {
    const res = await uploadKnowledge(file.value)
    message.value = res.message || (res.success ? '上传成功' : '完成')
    await loadSummary()
    chunks.value = []
    selectedSource.value = null
    viewAll.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploadLoading.value = false
  }
}

function formatFilterLabel() {
  if (viewAll.value) return '全部文件（分页）'
  if (selectedSource.value) return `源文件：${selectedSource.value}`
  return '未选择；在上方表格中点击「查看分块」，或使用「浏览全部」'
}

async function loadChunks(reset: boolean) {
  chunksError.value = ''
  chunksLoading.value = true
  if (reset) {
    chunkOffset.value = 0
    chunks.value = []
  }
  try {
    const res = await fetchKnowledgeChunks({
      source: viewAll.value || !selectedSource.value ? undefined : selectedSource.value,
      limit: pageSize,
      offset: reset ? 0 : chunkOffset.value,
    })
    if (reset) {
      chunks.value = res.chunks
    } else {
      chunks.value = [...chunks.value, ...res.chunks]
    }
    chunkOffset.value = res.offset + res.chunks.length
    chunksHasMore.value = res.has_more
    filterLabel.value = formatFilterLabel()
  } catch (e) {
    chunksError.value = e instanceof Error ? e.message : String(e)
  } finally {
    chunksLoading.value = false
  }
}

function selectSource(src: string) {
  viewAll.value = false
  selectedSource.value = src
  loadChunks(true)
}

function browseAll() {
  viewAll.value = true
  selectedSource.value = null
  loadChunks(true)
}

function loadMore() {
  if (!chunksHasMore.value || chunksLoading.value) return
  loadChunks(false)
}

onMounted(() => {
  loadSummary()
})
</script>

<template>
  <LearningModuleShell>
  <div class="view-knowledge">
    <div class="view-hero">
      <h1>知识库</h1>
      <p class="lead">
        上传 Markdown 到向量库（<code>POST /api/knowledge/upload</code>），并查看已入库的源文件与文本块（只读预览）。
      </p>
    </div>

    <section class="card">
      <h2 class="section-title">上传</h2>
      <label>选择 Markdown 文件</label>
      <div class="upload-zone">
        <input type="file" accept=".md" @change="onFile" />
      </div>

      <div class="btn-row field-gap">
        <button type="button" :disabled="uploadLoading || !file" @click="onUpload">
          {{ uploadLoading ? '上传中…' : '上传到向量库' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message" class="msg-success">{{ message }}</p>
    </section>

    <section class="card">
      <div class="section-head">
        <h2 class="section-title kb-head">已入库概览</h2>
        <button type="button" class="secondary" :disabled="summaryLoading" @click="loadSummary">
          {{ summaryLoading ? '刷新中…' : '刷新' }}
        </button>
      </div>
      <p v-if="summaryError" class="error">{{ summaryError }}</p>
      <p v-else-if="summary && !summaryLoading" class="meta">
        共 <strong>{{ summary.total_chunks }}</strong> 条向量块；来自
        <strong>{{ summary.sources.length }}</strong> 个源文件。
      </p>
      <div v-if="summary && summary.sources.length" class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>源文件</th>
              <th>块数</th>
              <th>上传日期</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in summary.sources"
              :key="s.source"
              :class="{ active: selectedSource === s.source && !viewAll }"
            >
              <td><code>{{ s.source }}</code></td>
              <td>{{ s.chunk_count }}</td>
              <td>{{ s.upload_date ?? '—' }}</td>
              <td>
                <button type="button" class="secondary" @click="selectSource(s.source)">查看分块</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="summary && !summary.sources.length" class="meta">暂无数据，请先上传 .md 文件。</p>
    </section>

    <section class="card">
      <div class="section-head">
        <h2 class="section-title kb-head">文本块（预览）</h2>
        <button
          v-if="summary && summary.total_chunks > 0"
          type="button"
          class="secondary"
          :disabled="chunksLoading"
          @click="browseAll"
        >
          浏览全部（分页）
        </button>
      </div>
      <p class="meta">{{ filterLabel || '在上方选择「查看分块」或「浏览全部」' }}</p>
      <p v-if="chunksError" class="error">{{ chunksError }}</p>
      <p v-if="chunksLoading && chunks.length === 0" class="meta">加载中…</p>

      <ul v-if="chunks.length" class="chunk-list">
        <li v-for="(c, i) in chunks" :key="c.id" class="chunk-item">
          <div class="chunk-head">
            <span class="chunk-badge">#{{ i + 1 }}</span>
            <code v-if="c.source">{{ c.source }}</code>
            <span v-if="c.upload_date" class="muted-tiny">{{ c.upload_date }}</span>
            <span class="muted-tiny">id: {{ c.id.slice(0, 8) }}… · {{ c.text_length }} 字</span>
          </div>
          <pre class="chunk-pre">{{ c.text_preview }}</pre>
        </li>
      </ul>

      <div v-if="chunks.length && chunksHasMore" class="btn-row field-gap">
        <button type="button" :disabled="chunksLoading" @click="loadMore">
          {{ chunksLoading ? '加载中…' : '加载更多' }}
        </button>
      </div>
    </section>
  </div>
  </LearningModuleShell>
</template>

<style scoped>
.kb-head {
  margin: 0;
}
</style>
