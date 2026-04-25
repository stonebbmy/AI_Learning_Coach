<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const title = computed(() => String(route.meta.title ?? '嵌入页面'))

const url = computed(() => {
  const key = route.meta.urlKey as string | undefined
  const def = String(route.meta.defaultUrl ?? '')
  if (!key) return def
  const v = (import.meta.env as Record<string, string | undefined>)[key]
  const s = (typeof v === 'string' ? v : '').trim()
  return s || def
})
</script>

<template>
  <div class="embed-page">
    <p v-if="!url" class="embed-placeholder">
      未配置嵌入地址。请在 <code>web/.env</code> 中设置
      <code>{{ route.meta.urlKey }}</code>（或保留路由 <code>meta.defaultUrl</code>）。
    </p>
    <iframe
      v-else
      class="embed-iframe"
      :src="url"
      :title="title"
      referrerpolicy="no-referrer-when-downgrade"
    />
  </div>
</template>

<style scoped>
.embed-page {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
}
.embed-iframe {
  flex: 1 1 0;
  min-height: 0;
  width: 100%;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
}
.embed-placeholder {
  margin: 0;
  padding: 1rem;
  color: var(--muted);
  font-size: 0.9rem;
}
</style>
