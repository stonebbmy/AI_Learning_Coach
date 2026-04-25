<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  generateOutline,
  confirmOutline,
  toOutlineConfirmBody,
  updateTutorContext,
  fetchOutlineList,
  deleteOutlineApi,
  type OutlineGenerateResponse,
  type StudyOutlineListItem,
} from '@/lib/api'
import { RouterLink } from 'vue-router'
import { userStore } from '@/lib/userStore'
import LearningModuleShell from '@/components/LearningModuleShell.vue'

const router = useRouter()

const target = ref('在 3 个月内从 Java 后端转向 AI 应用开发，掌握 LangChain、RAG 与 Agent 工程化')
const deadline = ref('3个月')

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const outline = ref<OutlineGenerateResponse | null>(null)
const savedId = ref<number | null>(userStore.state.currentOutlineId)

const listLoading = ref(false)
const listError = ref('')
const savedList = ref<StudyOutlineListItem[]>([])
const applyingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const toast = ref('')

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => {
    toast.value = ''
  }, 4200)
}

async function loadList() {
  listError.value = ''
  listLoading.value = true
  try {
    savedList.value = await fetchOutlineList()
  } catch (e) {
    listError.value = e instanceof Error ? e.message : String(e)
    savedList.value = []
  } finally {
    listLoading.value = false
  }
}

onMounted(() => {
  void loadList()
})

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
    const chapters = outline.value?.chapters.map((c) => c.chapter_title) ?? []
    userStore.setOutlineChapters(chapters)
    updateTutorContext({
      currentOutlineId: id,
      outlineChapters: chapters,
    }).catch(() => { /* 静默失败 */ })
    await loadList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

async function useAsCurrent(item: StudyOutlineListItem) {
  if (!item.id) return
  applyingId.value = item.id
  listError.value = ''
  try {
    userStore.setOutlineId(item.id)
    const chapters = (item.chapters ?? []).map((c) => c.chapterTitle)
    userStore.setOutlineChapters(chapters)
    await updateTutorContext({
      currentOutlineId: item.id,
      outlineChapters: chapters,
    })
    showToast('已设为当前并同步到私教。可点当前行「去今日计划」或下方按钮前往。')
  } catch (e) {
    listError.value = e instanceof Error ? e.message : String(e)
  } finally {
    applyingId.value = null
  }
}

async function onDeleteOutline(item: StudyOutlineListItem) {
  if (!item.id) return
  if (
    !confirm(
      `确定删除大纲「${item.title}」？\n此操作不可恢复。历史日计划中记录的「来源大纲 ID」会清空，任务行不删除。`,
    )
  ) {
    return
  }
  listError.value = ''
  deletingId.value = item.id
  try {
    await deleteOutlineApi(item.id)
    if (userStore.state.currentOutlineId === item.id) {
      userStore.setOutlineId(null)
      userStore.setOutlineChapters([])
      userStore.clearPlanState()
      await updateTutorContext({
        currentOutlineId: null,
        outlineChapters: [],
        currentPlanId: null,
        planTasks: [],
        progressRate: 0,
      })
    }
    showToast('已删除该大纲。')
    await loadList()
  } catch (e) {
    listError.value = e instanceof Error ? e.message : String(e)
  } finally {
    deletingId.value = null
  }
}
</script>

<template>
  <LearningModuleShell>
  <div class="view-outline">
    <div class="view-hero">
      <h1>学习大纲</h1>
      <p class="lead">
        在下方生成新大纲并确认后写入数据库；或从已保存列表中选定「当前使用的大纲」并同步到私教（Redis）。
      </p>
    </div>
    <p v-if="toast" class="toast-line">{{ toast }}</p>

    <div v-if="listLoading" class="card state-card">加载已保存大纲…</div>
    <div v-else class="card">
      <h2 class="section-title">已保存的大纲</h2>
      <p v-if="listError" class="error">{{ listError }}</p>
      <p v-else-if="!savedList.length" class="empty-hint">
        暂无已确认的大纲。可先生成并确认，或回到
        <router-link to="/">私教</router-link>
        通过「想学 XXX」走大纲卡片落库。
      </p>
      <ul v-else class="outline-list">
        <li
          v-for="o in savedList"
          :key="o.id"
          class="outline-list-item"
          :class="{ current: userStore.state.currentOutlineId === o.id }"
        >
          <div>
            <strong>{{ o.title }}</strong>
            <span v-if="userStore.state.currentOutlineId === o.id" class="badge">当前使用</span>
            <p class="meta">{{ o.overview?.slice(0, 120) }}{{ (o.overview?.length || 0) > 120 ? '…' : '' }}</p>
            <p class="meta">ID: {{ o.id }} · 章节数 {{ o.chapters?.length ?? 0 }}</p>
          </div>
          <div class="outline-actions">
            <button
              type="button"
              class="secondary"
              :disabled="applyingId === o.id || userStore.state.currentOutlineId === o.id"
              @click="useAsCurrent(o)"
            >
              {{ applyingId === o.id ? '同步中…' : (userStore.state.currentOutlineId === o.id ? '已选' : '设为当前并同步私教') }}
            </button>
            <RouterLink
              v-if="userStore.state.currentOutlineId === o.id"
              class="to-plan"
              :to="{ path: '/plan', query: { fromOutline: '1' } }"
            >去今日计划</RouterLink>
            <button
              type="button"
              class="link-danger"
              :disabled="deletingId === o.id"
              @click="onDeleteOutline(o)"
            >
              {{ deletingId === o.id ? '删除中…' : '删除' }}
            </button>
          </div>
        </li>
      </ul>
    </div>

    <div class="card card--stack">
      <h2 class="section-title">生成新大纲</h2>
      <label>学习目标</label>
      <textarea v-model="target" rows="3" />

      <label class="label-tight">期限</label>
      <input v-model="deadline" type="text" placeholder="例如：3个月" />

      <div class="field-gap">
        <button type="button" :disabled="loading || !target.trim()" @click="onGenerate">
          {{ loading ? '生成中…' : '生成大纲' }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="outline" class="card card--stack">
      <h2>{{ outline.title }}</h2>
      <p>{{ outline.overview }}</p>

      <div v-for="(ch, i) in outline.chapters" :key="i" class="chapter">
        <h3>{{ ch.chapter_title }}</h3>
        <p class="ch-desc">{{ ch.description }}</p>
        <ul>
          <li v-for="(kp, j) in ch.key_points" :key="j">{{ kp }}</li>
        </ul>
      </div>

      <button type="button" class="secondary" :disabled="saving" @click="onConfirm">
        {{ saving ? '保存中…' : '确认并保存到数据库' }}
      </button>
      <p v-if="savedId !== null" class="save-meta">
        已保存，大纲 ID：{{ savedId }}（已关联到账户，生成计划时将自动带入章节）
      </p>

      <div v-if="savedId" class="field-gap">
        <button type="button" @click="router.push({ path: '/plan', query: { fromOutline: '1' } })">
          去制定今日计划 →
        </button>
      </div>
    </div>
  </div>
  </LearningModuleShell>
</template>

<style scoped>
.outline-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.outline-list-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border, #2e3450);
  border-radius: 8px;
  background: var(--page-bg, #121520);
}
.outline-list-item.current {
  border-color: #5b72e8;
}
.badge {
  display: inline-block;
  margin-left: 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: #8ab4f8;
  vertical-align: middle;
}
.meta {
  font-size: 0.85rem;
  color: var(--muted);
  margin: 0.25rem 0 0;
}
.toast-line {
  margin: 0.5rem 0 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(59, 77, 184, 0.2);
  border: 1px solid rgba(138, 180, 248, 0.35);
  color: #c8d6f7;
  font-size: 0.9rem;
}
.outline-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  flex-shrink: 0;
}
.to-plan {
  font-size: 0.85rem;
  color: #8ab4f8;
  text-decoration: none;
}
.to-plan:hover {
  text-decoration: underline;
}
.link-danger {
  background: none;
  border: none;
  color: #f87171;
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}
.ch-desc {
  color: var(--muted);
  margin: 0;
  font-size: 0.95rem;
}
.empty-hint {
  color: var(--muted);
}
.save-meta {
  margin-top: 0.75rem;
  color: var(--muted);
  font-size: 0.9rem;
}
</style>
