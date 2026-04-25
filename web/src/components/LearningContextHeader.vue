<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { userStore } from '../lib/userStore'
import { fetchOutlineList, type StudyOutlineListItem } from '../lib/api'

defineProps<{
  /** 与计划页输入框一致，仅展示用 */
  goalText: string
}>()

const list = ref<StudyOutlineListItem[]>([])
const loading = ref(false)
const expanded = ref(true)

const current = computed(() => {
  const id = userStore.state.currentOutlineId
  if (id == null) return null
  return list.value.find((o) => o.id === id) ?? null
})

const chapterPreview = computed(() => {
  const ch = current.value?.chapters ?? []
  return ch.slice(0, 6)
})

async function load() {
  loading.value = true
  try {
    list.value = await fetchOutlineList()
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => userStore.state.currentOutlineId,
  () => {
    void load()
  },
)
</script>

<template>
  <div class="lch">
    <div class="lch-row">
      <span class="lch-label">当前大纲</span>
      <div v-if="loading" class="lch-muted">加载中…</div>
      <div v-else-if="!userStore.state.currentOutlineId" class="lch-empty">
        未选择已保存的大纲。请先在
        <RouterLink to="/outline">学习大纲</RouterLink>
        中「设为当前并同步私教」。
      </div>
      <div v-else-if="!current" class="lch-warn">
        本地已记录大纲 #{{ userStore.state.currentOutlineId }}，但列表中未找到（可
        <a href="#" @click.prevent="load()">刷新</a>）。
      </div>
      <div v-else class="lch-outline">
        <strong>{{ current.title }}</strong>
        <span class="lch-id">#{{ current.id }}</span>
        <button type="button" class="lch-toggle" @click="expanded = !expanded">
          {{ expanded ? '收起章节' : '展开章节' }}
        </button>
        <ul v-show="expanded" class="lch-chapters">
          <li v-for="(c, i) in chapterPreview" :key="i">
            <span class="lch-ord">{{ i + 1 }}.</span> {{ c.chapterTitle }}
          </li>
          <li v-if="(current.chapters?.length ?? 0) > 6" class="lch-muted">… 共 {{ current.chapters?.length }} 章</li>
        </ul>
      </div>
    </div>
    <div class="lch-row">
      <span class="lch-label">今日目标</span>
      <p class="lch-goal">{{ goalText || '（未填写）' }}</p>
    </div>
  </div>
</template>

<style scoped>
.lch {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  background: var(--page-bg, #0f111a);
  border: 1px solid var(--border, #2e3450);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.lch-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.lch-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted, #8899cc);
}
.lch-muted {
  font-size: 0.9rem;
  color: var(--muted);
}
.lch-empty,
.lch-warn {
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--text, #e0e6f7);
}
.lch-warn {
  color: #fbbf24;
}
.lch-id {
  margin-left: 0.4rem;
  font-size: 0.8rem;
  color: var(--muted);
  font-weight: 400;
}
.lch-toggle {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  padding: 1px 8px;
  background: var(--card-bg, #1e2233);
  border: 1px solid var(--border, #2e3450);
  color: #8ab4f8;
  border-radius: 4px;
  cursor: pointer;
}
.lch-chapters {
  margin: 0.4rem 0 0 1.2rem;
  padding: 0;
  font-size: 0.85rem;
  color: var(--muted, #aabbcc);
  line-height: 1.45;
}
.lch-ord {
  color: #5b72e8;
  font-weight: 600;
  margin-right: 0.25rem;
}
.lch-goal {
  margin: 0;
  font-size: 0.92rem;
  color: var(--text, #e0e6f7);
  line-height: 1.4;
  word-break: break-word;
}
a {
  color: #8ab4f8;
}
</style>
